import urllib3
import io
import shutil
import os

import zipfile

print("Download UPX")
http = urllib3.PoolManager()
with http.request("GET", "https://github.com/upx/upx/releases/download/v4.0.2/upx-4.0.2-win64.zip") as r:
	with zipfile.ZipFile(io.BytesIO(r.data)) as z:
		for file in z.infolist():
			if ("upx.exe" in file.filename):
				with z.open(file.filename) as zf:
					with open("upx.exe", "wb") as f:
						shutil.copyfileobj(zf, f)
						break

print("Building")
os.system("python -m venv buildenv")
os.system("buildenv\\Scripts\\activate.bat")
os.system("pip install -r requirements.txt --prefer-binary")
os.system("pyinstaller kinter.spec")

print("Download FFMpeg")
with http.request("GET", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip") as r:
	with zipfile.ZipFile(io.BytesIO(r.data)) as z:
		for file in z.infolist():
			if ("ffmpeg.exe" in file.filename):
				with z.open(file.filename) as zf:
					with open("dist/ffmpeg.exe", "wb") as f:
						shutil.copyfileobj(zf, f)
						break

print("Done!")