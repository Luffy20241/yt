import asyncio
import os

async def compress_video(input_path, output_path, ffmpeg_code):
    # Ensure the output path is set to overwrite
    cmd = f'vegapunk -y -i "{input_path}" {ffmpeg_code} "{output_path}"'
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        print(f"FFmpeg error: {stderr.decode().strip()}")
    return os.path.exists(output_path)

