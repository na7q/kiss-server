# kiss-server
This script allows you to connect to any KISS TNC Modem like VARA with unlimited KISS clients. VARA usually only allows a single connection and this server fixes that.
The sever acts as a man in the middle forwarding traffic bidirectionally between the clients and the modem.

Simply change the VARA IP& Ports to your VARA session, and change the Server IP and Port to your needs. Use 0.0.0.0 to bind all IPs.

Then just run the script within terminal or double click within Windows to start.

Run in the background using "screen":
screen -dmS kiss python3.9 /home/aprs/server.py

View screen:
screen -r kiss

Exit screen (detach):
ctrl a then ctrl d
