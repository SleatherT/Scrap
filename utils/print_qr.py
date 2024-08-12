import qrcode

def print_qr(data):
    # Create the QR code
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Generate the QR code
    qr_code_matrix = qr.get_matrix()
    
    # Print the QR code in the terminal using Unicode characters
    for row1, row2 in zip(qr_code_matrix[::2], qr_code_matrix[1::2]):
        line = ""
        
        for col1, col2 in zip(row1, row2):
            if col1 and col2:
                line += "█"  # Full block
            elif col1:
                line += "▀"  # Top half block
            elif col2:
                line += "▄"  # Bottom half block
            else:
                line += " "  # Space
        print(line)

