import socket
import threading
from datetime import datetime
import signal
import sys

KISS_FEND = 0xC0
KISS_FESC = 0xDB
KISS_TFEND = 0xDC
KISS_TFESC = 0xDD

#VARA
DESTINATION_IP = "0.0.0.1"
DESTINATION_PORT = 8200

#Multi Connection Server
SERVER_IP = "0.0.0.0"
SERVER_PORT = 8201

def decode_address(encoded_data):
    call = "".join([chr(byte >> 1) for byte in encoded_data[:6]]).rstrip()
    ssid = (encoded_data[6] >> 1) & 0b00001111
    
    if ssid == 0:
        address = call
    else:
        address = f"{call}-{ssid}"

    return address

def decode_kiss_frame(kiss_frame, formatted_time):
    decoded_packet = []
    is_escaping = False

    for byte in kiss_frame:
        if is_escaping:
            if byte == KISS_TFEND:
                decoded_packet.append(KISS_FEND)
            elif byte == KISS_TFESC:
                decoded_packet.append(KISS_FESC)
            else:
                # Invalid escape sequence, ignore or handle as needed
                pass
            is_escaping = False
        else:
            if byte == KISS_FEND:
                if 0x03 in decoded_packet:
                    c_index = decoded_packet.index(0x03)
                    if c_index + 1 < len(decoded_packet):
                        pid = decoded_packet[c_index + 1]
                        ax25_data = bytes(decoded_packet[c_index + 2:])

                        if ax25_data and ax25_data[-1] == 0x0A:
                            ax25_data = ax25_data[:-1] + bytes([0x0D])

                        dest_addr_encoded = decoded_packet[1:8]
                        src_addr_encoded = decoded_packet[8:15]
                        src_addr = decode_address(src_addr_encoded)
                        dest_addr = decode_address(dest_addr_encoded)

                        paths_start = 15
                        paths_end = decoded_packet.index(0x03)
                        paths = decoded_packet[paths_start:paths_end]

                        if paths:
                            path_addresses = []
                            path_addresses_with_asterisk = []
                            for i in range(0, len(paths), 7):
                                path_chunk = paths[i:i+7]
                                path_address = decode_address(path_chunk)

                                if path_chunk[-1] in [0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9]:
                                    path_address_with_asterisk = f"{path_address}*"
                                else:
                                    path_address_with_asterisk = path_address

                                path_addresses.append(path_address)
                                path_addresses_with_asterisk.append(path_address_with_asterisk)

                            path_addresses_str = ','.join(path_addresses_with_asterisk)
                        else:
                            path_addresses_str = ""

                        if path_addresses_str:
                            packet = f"{src_addr}>{dest_addr},{path_addresses_str}:{ax25_data.decode('ascii', errors='ignore')}"
                        else:
                            packet = f"{src_addr}>{dest_addr}:{ax25_data.decode('ascii', errors='ignore')}"

                        print(f"{formatted_time}: {packet}")

            elif byte == KISS_FESC:
                is_escaping = True
            else:
                decoded_packet.append(byte)

def forward_data_to_destination(data, destination_socket):
    # Forward the received data to the destination server
    destination_socket.sendall(data)

def handle_client(client_socket, destination_socket):
    frame_buffer = []

    while True:
        data = client_socket.recv(1024)
        if not data:
            break

        frame_buffer.extend(data)
        if KISS_FEND in frame_buffer:
            hex_data = ' '.join([hex(b)[2:].zfill(2) for b in frame_buffer])
            formatted_time = datetime.now().strftime("%H:%M:%S")
            decode_kiss_frame(frame_buffer, formatted_time)

            # Forward the received data to the destination server
            forward_data_to_destination(data, destination_socket)

            frame_buffer = []

    client_socket.close()

def listen_and_forward(destination_socket, client_sockets):
    while True:
        data = destination_socket.recv(1024)
        if not data:
            break

        # Print the data received from the destination socket
        formatted_time = datetime.now().strftime("%H:%M:%S")
        decode_kiss_frame(data, formatted_time)
        
        # Forward the received data to all connected clients
        to_remove = []
        for client_socket in client_sockets:
            try:
                client_socket.sendall(data)
            except BrokenPipeError:
                # Handle the case when a client socket is closed
                to_remove.append(client_socket)

        # Remove closed client sockets from the list
        for client_socket in to_remove:
            print(f"Removing closed client socket: {client_socket}")
            client_sockets.remove(client_socket)

def connect_to_destination():
    destination_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    destination_socket.connect((DESTINATION_IP, DESTINATION_PORT))
    return destination_socket

def start_server():
    # Create a server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((SERVER_IP, SERVER_PORT))
    server.listen(5)

    print("Server listening on port 8201.")
    
    # Declare destination_socket as a global variable
    global destination_socket
    destination_socket = connect_to_destination()

    client_sockets = []

    # Start a thread to listen for data from the destination socket and forward it to clients
    listener_thread = threading.Thread(target=listen_and_forward, args=(destination_socket, client_sockets))
    listener_thread.start()

    while True:
        try:
            client_socket, addr = server.accept()
            print(f"Accepted connection from {addr}")
            client_sockets.append(client_socket)

            # Start a thread to handle each client
            client_handler = threading.Thread(target=handle_client, args=(client_socket, destination_socket))
            client_handler.start()
        except KeyboardInterrupt:
            print("Server shutting down...")
            server.close()
            destination_socket.close()
            sys.exit()
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    start_server()
