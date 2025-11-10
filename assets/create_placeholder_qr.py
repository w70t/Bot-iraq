#!/usr/bin/env python3
"""
Create a placeholder QR code image
User should replace this with their actual Binance QR code
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    
    # Create a 500x500 white image
    img = Image.new('RGB', (500, 500), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw a simple border
    draw.rectangle([10, 10, 490, 490], outline='black', width=3)
    
    # Add text
    text_lines = [
        "Binance Pay QR Code",
        "",
        "Pay ID: 86847466",
        "",
        "Replace this image with",
        "your actual Binance QR code",
        "",
        "File: assets/binance_qr.jpeg"
    ]
    
    y_position = 100
    for line in text_lines:
        # Calculate text position to center it
        bbox = draw.textbbox((0, 0), line)
        text_width = bbox[2] - bbox[0]
        x_position = (500 - text_width) // 2
        
        draw.text((x_position, y_position), line, fill='black')
        y_position += 35
    
    # Save the image
    img.save('/home/user/Bot-iraq/assets/binance_qr.jpeg', 'JPEG')
    print("✅ Placeholder QR code created successfully!")
    
except ImportError:
    print("⚠️ PIL/Pillow not installed. Creating a simple text file instead.")
    with open('/home/user/Bot-iraq/assets/binance_qr_placeholder.txt', 'w') as f:
        f.write("Place your Binance Pay QR code here as: binance_qr.jpeg\n")
        f.write("Pay ID: 86847466\n")
