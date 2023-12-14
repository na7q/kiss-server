# kiss-server
This script allows you to connect to any KISS TNC Modem like VARA with unlimited KISS clients. VARA usually only allows a single connection and this server fixes that.<br>
The sever acts as a man in the middle forwarding traffic bidirectionally between the clients and the modem.
<br>
Simply change the VARA IP& Ports to your VARA session, and change the Server IP and Port to your needs. Use 0.0.0.0 to bind all IPs.
<br>
Then just run the script within terminal or double click within Windows to start.
<br>
Run in the background using "screen":<br>
screen -dmS kiss python3.9 /home/aprs/server.py<br>

View screen:<br>
screen -r kiss<br>

Exit screen (detach):<br>
ctrl a then ctrl d
