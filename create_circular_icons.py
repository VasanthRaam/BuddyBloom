from PIL import Image, ImageDraw
import os

res_dir = r'C:\BuddyBloom\BuddyBloom\mobile\android\app\src\main\res'
assets_dir = r'C:\BuddyBloom\BuddyBloom\mobile\assets'
logo_path = r'C:\BuddyBloom\BuddyBloom\mobile\assets\app-logo.png'

def create_circular_icon(logo_path, dest_path, size):
    # 1. Create transparent base image
    base = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(base)
    
    # 2. Draw white circle
    # Leave 1px boundary to prevent anti-aliasing clipping
    draw.ellipse([2, 2, size - 2, size - 2], fill=(255, 255, 255, 255))
    
    # 3. Open logo and convert to RGBA
    logo = Image.open(logo_path)
    if logo.mode != 'RGBA':
        logo = logo.convert('RGBA')
        
    # 4. Resize logo to 70% of icon size to fit nicely with padding
    logo_size = int(size * 0.70)
    logo_resized = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    
    # 5. Calculate offset to center the logo
    offset = (size - logo_size) // 2
    
    # 6. Paste logo on top of the circle
    base.paste(logo_resized, (offset, offset), logo_resized)
    
    # 7. Save to destination
    ext = os.path.splitext(dest_path)[1].lower()
    if ext == '.webp':
        base.save(dest_path, 'WEBP')
    else:
        base.save(dest_path, 'PNG')

# 1. Update Assets directory (for Expo config / Web / Favicon)
create_circular_icon(logo_path, os.path.join(assets_dir, 'icon.png'), 1024)
create_circular_icon(logo_path, os.path.join(assets_dir, 'adaptive-icon.png'), 1024)
create_circular_icon(logo_path, os.path.join(assets_dir, 'splash-icon.png'), 1284)
create_circular_icon(logo_path, os.path.join(assets_dir, 'favicon.png'), 192)

# 2. Update Android native mipmaps (for native build APK)
sizes = {
    'mipmap-mdpi': (48, 108),
    'mipmap-hdpi': (72, 162),
    'mipmap-xhdpi': (96, 216),
    'mipmap-xxhdpi': (144, 324),
    'mipmap-xxxhdpi': (192, 432),
}

for folder, (size_icon, size_fg) in sizes.items():
    folder_path = os.path.join(res_dir, folder)
    
    # Regular launcher icon (circle)
    create_circular_icon(logo_path, os.path.join(folder_path, 'ic_launcher.webp'), size_icon)
    
    # Round launcher icon (circle)
    create_circular_icon(logo_path, os.path.join(folder_path, 'ic_launcher_round.webp'), size_icon)
    
    # Adaptive foreground icon
    # Since Android adaptive background is white, we make foreground just a transparent logo, or a circle
    create_circular_icon(logo_path, os.path.join(folder_path, 'ic_launcher_foreground.webp'), size_fg)

print('Circular icons successfully generated!')
