from PIL import Image
import os

assets_dir = r'C:\BuddyBloom\BuddyBloom\mobile\assets'
logo_path = os.path.join(assets_dir, 'app-logo.png')

img = Image.open(logo_path)

if img.mode != 'RGBA':
    img = img.convert('RGBA')

img_1024 = img.resize((1024, 1024), Image.Resampling.LANCZOS)
img_1024.save(os.path.join(assets_dir, 'icon.png'))
img_1024.save(os.path.join(assets_dir, 'adaptive-icon.png'))

img_1284 = img.resize((1284, 1284), Image.Resampling.LANCZOS)
img_1284.save(os.path.join(assets_dir, 'splash-icon.png'))

img_192 = img.resize((192, 192), Image.Resampling.LANCZOS)
img_192.save(os.path.join(assets_dir, 'favicon.png'))
print('Done')
