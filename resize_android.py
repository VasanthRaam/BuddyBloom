from PIL import Image
import os

res_dir = r'C:\BuddyBloom\BuddyBloom\mobile\android\app\src\main\res'
logo_path = r'C:\BuddyBloom\BuddyBloom\mobile\assets\app-logo.png'

img = Image.open(logo_path)
if img.mode != 'RGBA':
    img = img.convert('RGBA')

sizes = {
    'mipmap-mdpi': (48, 108),
    'mipmap-hdpi': (72, 162),
    'mipmap-xhdpi': (96, 216),
    'mipmap-xxhdpi': (144, 324),
    'mipmap-xxxhdpi': (192, 432),
}

for folder, (size_icon, size_fg) in sizes.items():
    folder_path = os.path.join(res_dir, folder)
    
    # Save as WebP
    img_icon = img.resize((size_icon, size_icon), Image.Resampling.LANCZOS)
    img_icon.save(os.path.join(folder_path, 'ic_launcher.webp'), 'WEBP')
    
    img_icon.save(os.path.join(folder_path, 'ic_launcher_round.webp'), 'WEBP')
    
    img_fg = img.resize((size_fg, size_fg), Image.Resampling.LANCZOS)
    img_fg.save(os.path.join(folder_path, 'ic_launcher_foreground.webp'), 'WEBP')

print('Android launcher WebP icons successfully replaced!')
