#!/usr/bin/env python3
"""
Script to generate placeholder PWA icons.
This creates simple SVG icons that can be converted to PNG for the PWA.
"""

import os
from pathlib import Path

def create_icon_svg(size, output_path):
    """Create a simple SVG icon for the well tank monitor"""
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="water" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#1d4ed8;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <!-- Background -->
  <rect width="{size}" height="{size}" rx="{size//8}" fill="url(#bg)"/>
  
  <!-- Tank -->
  <rect x="{size//4}" y="{size//6}" width="{size//2}" height="{size*2//3}" 
        rx="{size//20}" fill="none" stroke="white" stroke-width="{max(2, size//32)}"/>
  
  <!-- Water level -->
  <rect x="{size//4 + max(2, size//32)}" y="{size*5//6}" width="{size//2 - max(4, size//16)}" 
        height="{size//4}" fill="url(#water)" rx="{size//40}"/>
  
  <!-- Water drop icon -->
  <circle cx="{size//2}" cy="{size//3}" r="{size//8}" fill="white" opacity="0.9"/>
  <path d="M {size//2} {size//3 - size//8} Q {size//2 - size//12} {size//3 - size//6} {size//2} {size//3 + size//8} Q {size//2 + size//12} {size//3 - size//6} {size//2} {size//3 - size//8} Z" 
        fill="white" opacity="0.7"/>
</svg>'''
    
    with open(output_path, 'w') as f:
        f.write(svg_content)

def main():
    """Generate all required PWA icons"""
    # Create icons directory
    icons_dir = Path("frontend/icons")
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    # Icon sizes for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    print("Generating PWA icons...")
    
    for size in sizes:
        output_path = icons_dir / f"icon-{size}x{size}.svg"
        create_icon_svg(size, output_path)
        print(f"Created {output_path}")
    
    # Create screenshots directory
    screenshots_dir = Path("frontend/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    # Create placeholder screenshot SVGs
    desktop_screenshot = screenshots_dir / "desktop.svg"
    mobile_screenshot = screenshots_dir / "mobile.svg"
    
    # Desktop screenshot placeholder
    desktop_svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <rect width="1280" height="720" fill="#f0f0f0"/>
  <text x="640" y="360" text-anchor="middle" font-family="Arial, sans-serif" font-size="48" fill="#666">
    Desktop Screenshot Placeholder
  </text>
  <text x="640" y="420" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" fill="#999">
    Replace with actual screenshot
  </text>
</svg>'''
    
    with open(desktop_screenshot, 'w') as f:
        f.write(desktop_svg)
    
    # Mobile screenshot placeholder
    mobile_svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="390" height="844" viewBox="0 0 390 844" xmlns="http://www.w3.org/2000/svg">
  <rect width="390" height="844" fill="#f0f0f0"/>
  <text x="195" y="422" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" fill="#666">
    Mobile Screenshot Placeholder
  </text>
  <text x="195" y="460" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#999">
    Replace with actual screenshot
  </text>
</svg>'''
    
    with open(mobile_screenshot, 'w') as f:
        f.write(mobile_svg)
    
    print(f"Created {desktop_screenshot}")
    print(f"Created {mobile_screenshot}")
    print("\nIcon generation complete!")
    print("\nNote: These are SVG placeholders. For production, convert them to PNG:")
    print("You can use online tools like:")
    print("- https://convertio.co/svg-png/")
    print("- https://cloudconvert.com/svg-to-png")
    print("- Or use ImageMagick: convert icon.svg icon.png")

if __name__ == "__main__":
    main() 