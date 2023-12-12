import socket
import threading
from datetime import datetime
import signal
import sys
import time

# Constants
KISS_FEND = 0xC0
KISS_FESC = 0xDB
KISS_TFEND = 0xDC
KISS_TFESC = 0xDD

# Global VARA Socket Variable
vara_socket = None

vara_ip = "0.0.0.0"
vara_port = 8200

server_ip = "0.0.0.0"
server_port = 8201

def initialize_vara_socket():
    global vara_socket
    try:
        vara_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        vara_socket.connect((vara_ip, vara_port))  # Replace with the actual VARA server address and port
        print("VARA socket connected.")
    except Exception as e:
        print(f"Error initializing VARA socket: {e}")
        vara_socket = None

def handle_vara_reconnection():
    global vara_socket
    while True:
        if vara_socket is None:
            print("Reconnecting to VARA server...")
            initialize_vara_socket()
        time.sleep(5)  # Adjust the sleep duration based on your needs

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

def broadcast_to_clients(data, clients):
    for client_socket in clients:
        try:
            client_socket.sendall(data)
        except Exception as e:
            print(f"Error broadcasting data to client: {e}")

def handle_client(client_socket, clients_lock, clients):
    frame_buffer = []

    def receive_from_client():
        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    print("No more data from client. Closing connection.")
                    break

                frame_buffer.extend(data)

                if KISS_FEND in frame_buffer:
                    hex_data = ' '.join([hex(b)[2:].zfill(2) for b in frame_buffer])
                    formatted_time = datetime.now().strftime("%H:%M:%S")
                    decode_kiss_frame(frame_buffer, formatted_time)

                    # Forward the received data to the destination server
                    global vara_socket
                    if vara_socket:
                        vara_socket.sendall(data)

                    # Reset the frame buffer
                    frame_buffer.clear()

        except Exception as e:
            print(f"Error in receive_from_client: {e}")
        finally:
            with clients_lock:
                clients.remove(client_socket)
            client_socket.close()

    with clients_lock:
        clients.append(client_socket)

    client_to_vara_thread = threading.Thread(target=receive_from_client)
    client_to_vara_thread.start()

def receive_from_vara(clients_lock, clients):
    frame_buffer = []
    buffered_data = b""  # Buffer to store VARA data during disconnection

    while True:
        global vara_socket
        try:
            vara_data = vara_socket.recv(1024)
            if not vara_data:
                print("No more data from VARA socket. Attempting reconnection...")

                # Attempt reconnection
                initialize_vara_socket()

                if vara_socket is None:
                    print("Reconnection attempt failed. Waiting before the next attempt...")
                    time.sleep(5)  # Adjust the sleep duration based on your needs
                    continue  # Continue to the next iteration of the loop
                else:
                    print("Reconnection successful.")
                    # Broadcast buffered data to clients
                    with clients_lock:
                        broadcast_to_clients(buffered_data, clients)
                    buffered_data = b""  # Clear the buffer after broadcasting

            frame_buffer.extend(vara_data)

            if KISS_FEND in frame_buffer:
                formatted_time = datetime.now().strftime("%H:%M:%S")
                decode_kiss_frame(frame_buffer, formatted_time)

                # Broadcast VARA data to all connected clients
                with clients_lock:
                    broadcast_to_clients(vara_data, clients)

                # Reset the frame buffer
                frame_buffer.clear()

        except Exception as e:
            print(f"Error in receive_from_vara: {e}")
            # Buffer VARA data during disconnection
            buffered_data += vara_data
            time.sleep(5)  # Adjust the sleep duration based on your needs

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((server_ip, server_port))
    server.listen(5)

    print("Server listening on port 8201.")

    initialize_vara_socket()  # Initialize VARA socket on script start

    clients = []
    clients_lock = threading.Lock()

    try:
        # Start a thread to handle VARA reconnection
        reconnection_thread = threading.Thread(target=handle_vara_reconnection)
        reconnection_thread.start()

        # Start a thread to receive and handle VARA data
        vara_thread = threading.Thread(target=receive_from_vara, args=(clients_lock, clients))
        vara_thread.start()

        while True:
            # Accept client connection
            client_socket, addr = server.accept()
            print(f"Accepted connection from {addr}")

            # Handle the client in a separate thread
            client_handler = threading.Thread(target=handle_client, args=(client_socket, clients_lock, clients))
            client_handler.start()

    except KeyboardInterrupt:
        print("Server shutting down...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()
