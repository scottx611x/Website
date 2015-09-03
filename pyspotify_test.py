#Spotify Playlist track de-duplicator
import spotify, threading, sys

logged_in_event = threading.Event()

USERNAME = str(sys.argv[1])
PASSWORD = str(sys.argv[2])
PLAYLIST_URI = str(sys.argv[3])

def connection_state_listener(session):
    if session.connection.state is spotify.ConnectionState.LOGGED_IN:
        logged_in_event.set()

session = spotify.Session()
session.on(
    spotify.SessionEvent.CONNECTION_STATE_UPDATED,
    connection_state_listener)

#pass username and password from web
session.login(USERNAME, PASSWORD)
session.connection.state

while not logged_in_event.wait(0.1):
    session.process_events()
session.connection.state


#pass in playlist name from web
playlist = session.get_playlist(PLAYLIST_URI)
pl_name = playlist.load().name

tracks = playlist.tracks

x=0
for track in tracks:
    x += 1
with open("PLAYLIST","w+") as P:
    P.write("<html>")
    P.write("<body>")
    P.write("<br><br>")
    P.write("<div align='center'>")
    P.write("<p>%s logged in.</p>" % session.user_name) 
    P.write("<p>%d Tracks total</p>" % x) 

    tracks = list(set(tracks))

    x=0
    for track in tracks:
        x += 1
    P.write("<p>%d Tracks after removing duplicates</p>" % x) 

    P.write("</div>")
    P.write("</body>")
    P.write("</html>")

#New_Playlist = raw_input("Please enter a name for the new playlist: ")

