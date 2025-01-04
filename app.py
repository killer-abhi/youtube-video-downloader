from flask import Flask, request, render_template, jsonify, Response, send_from_directory
import yt_dlp
import os
import uuid

# from google.cloud import storage

app = Flask(__name__)

# Directory to store downloaded videos temporarily
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Route to serve the form
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# Route to fetch video info (title, thumbnail, qualities)
@app.route("/get_video_info", methods=["GET"])
def get_video_info():
    youtube_url = request.args.get("url")
    if not youtube_url:
        return jsonify({"error": "No URL provided"}), 400
    if youtube_url.count("playlist"):
        return jsonify({"error": "Playlist URLs are not supported"}), 400
    try:
        with yt_dlp.YoutubeDL() as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            formats = info.get("formats", [])
            title = info.get("title", "Unknown Title")
            thumbnail = info.get("thumbnail", "")

            # Fetch available qualities
            quality_dict = {}
            quality_ranges = [
                (180, 280, "240p"),
                (281, 380, "360p"),
                (381, 480, "480p"),
                (481, 720, "720p"),
                (721, 1080, "1080p"),
                (1081, 1440, "1440p (2K)"),
                (1441, 2160, "2160p (4K)"),
            ]

            def map_quality(height):
                for min_h, max_h, label in quality_ranges:
                    if min_h <= height <= max_h:
                        return label
                return f"{height}px"

            for f in formats:
                height = f.get("height")
                if not height:
                    continue
                if height < 180:
                    continue

                quality_label = map_quality(height)
                size = f.get("filesize", f.get("filesize_approx"))
                if size:
                    size = round(size / (1024 * 1024), 2)  # Convert to MB

                # Filter for qualities with size less than 500 MB
                if size:
                    if quality_label not in quality_dict or (
                        size is not None
                        and (
                            quality_dict[quality_label].get("size") is None
                            or size > quality_dict[quality_label]["size"]
                        )
                    ):
                        quality_dict[quality_label] = {
                            "quality": quality_label,
                            "size": size,
                        }

            # Sort qualities
            sorted_qualities = sorted(
                quality_dict.values(),
                key=lambda x: next(
                    (
                        i
                        for i, (_, _, label) in enumerate(quality_ranges)
                        if label == x["quality"]
                    ),
                    float("inf"),
                ),
            )

            return jsonify(
                {"title": title, "thumbnail": thumbnail, "qualities": sorted_qualities}
            )

    except Exception as e:
        print(f"Error fetching video info: {e}")
        return (
            jsonify({"error": "Failed to fetch video info. Please try again later."}),
            500,
        )


# Route to fetch available qualities (kept for compatibility)
@app.route("/get_quality", methods=["GET"])
def get_quality():
    return get_video_info()


# Route to handle video download
@app.route("/download", methods=["POST"])
def download_video():
    youtube_url = request.form.get("youtube_url")
    if youtube_url.count("playlist"):
        return jsonify({"error": "Playlist URLs are not supported"}), 400
    selected_quality = request.form.get("quality")

    if not youtube_url:
        return jsonify({"error": "No URL provided"}), 400
    if not selected_quality:
        return jsonify({"error": "No quality selected"}), 400

    try:
        # video_file = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_video.mp4")
        # audio_file = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_audio.mp4")
        final_file = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
        with yt_dlp.YoutubeDL() as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            formats = info.get("formats", [])

        quality_ranges = {
            "240p": (180, 280),
            "360p": (281, 380),
            "480p": (381, 480),
            "720p": (481, 720),
            "1080p": (721, 1080),
            "1440p (2K)": (1081, 1440),
            "2160p (4K)": (1441, 2160),
        }
        min_height, max_height = quality_ranges.get(selected_quality, (0, 0))

        # Select the best matching video format
        selected_video_format = None
        for f in formats:
            height = f.get("height")
            if height and min_height <= height <= max_height:
                if f.get("vcodec") != "none":
                    selected_video_format = f
                    break

        if not selected_video_format:
            return (
                jsonify(
                    {"error": f"Selected quality {selected_quality} not available"}
                ),
                400,
            )

        # Select the best audio format
        best_audio_format = None
        for f in formats:
            if f.get("acodec") != "none" and f.get("vcodec") == "none":
                best_audio_format = f
                break

        if not best_audio_format:
            return jsonify({"error": "No suitable audio format found"}), 400

        # yt-dlp options for downloading and merging
        ydl_opts = {
            "format": f"{selected_video_format['format_id']}+{best_audio_format['format_id']}",  # Combine video and audio formats
            "outtmpl": final_file,  # Output template
            "merge_output_format": "mp4",  # Ensure the output is in MP4 format
            "noplaylist": True,  # Avoid downloading entire playlists if the URL is for a playlist
        }

        # Use yt-dlp to download and merge
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
            
        ydl_opts = {
            "format": f"{selected_video_format['format_id']}+{best_audio_format['format_id']}",  # Combine video and audio formats
            "outtmpl": final_file,  # Output template
            "merge_output_format": "mp4",  # Ensure the output is in MP4 format
            "noplaylist": True,  # Avoid downloading entire playlists if the URL is for a playlist
        }

        official_title = info.get("title", "video").replace("/", "_")

        def generate_file_chunks(file_path, chunk_size=30 * 1024 * 1024):  # 30 MB
            try:
                with open(file_path, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            finally:
                # Cleanup after all chunks are served
                if os.path.exists(file_path):
                    os.remove(file_path)

        return Response(
                generate_file_chunks(final_file),
                headers={
                    "Content-Disposition": f"attachment; filename={official_title}_{selected_quality}.mp4",
                    "Content-Type": "video/mp4",
                },
            )

    except Exception as e:
        print(f"Error: {e}")
        return (
            jsonify(
                {"error": "Failed to download and merge video. Please try again later."}
            ),
            500,
        )


if __name__ == "__main__":
    # Use port 8080 for Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
