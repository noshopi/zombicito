ZOMBIES ATE MY NEIGHBORS - NATIVE EDITION (LAN + ONLINE)
========================================================
A from-scratch NATIVE Windows remake in C + SDL2. No emulator.
One player per PC - multiplayer runs over your LAN or on the public
dedicated server (zombicito.duckdns.org:6969).

HOW TO PLAY
  Double-click  ..\ZombiesAteMyNeighbors.exe   (project root)
  ONE single file - assets and SDL2 are embedded inside. Copy just this
  .exe to any Windows PC (USB, network share, whatever) and it runs.
  (Zamn.exe is the developer build in this folder.)
  The game AUTO-CONNECTS to the public server when it opens. Press Esc
  to leave the lobby and play locally instead.

MENU
  SINGLE PLAYER ... pick Zeke or Julie, rescue 12 neighbors, reach the
                    EXIT door on the top-left house
  MULTIPLAYER ..... opens the LOBBY
  OPTIONS ......... fullscreen, pixel filter, SFX volume

MULTIPLAYER LOBBY (one human per PC)
  1. Pick the mode with LEFT/RIGHT:  4 TEAMS OF 2  or  2 TEAMS OF 2
  2. One PC selects HOST GAME (the lobby shows that PC's LAN IP)
  3. Everyone else can:
       - JOIN (default address zombicito.duckdns.org - the public server)
       - BROWSE GAMES - hosts announce themselves on the LAN, so local
         games show up automatically (name, mode, players). Select with
         UP/DOWN and press Enter.
  4. StarCraft-style table: pick any slot, choose TEAM (LEFT/RIGHT) and
     CHARACTER (C or X). The host can also set bots' slots.
  5. Host presses Enter to start
   Teams: GREEN, RED, BLUE, YELLOW - each team fields a Zeke + a Julie.
   Teams spawn in front of their quadrant's house. Zombies rise from the
   lawn edges around houses; medkits (8 on the map) respawn after 25s.
   Most neighbors rescued wins (score breaks ties). Squirt rival players
   to STUN them. Standings screen when the last neighbor is resolved.
   The camera always follows YOUR character ("YOU" floats above it).

PUBLIC DEDICATED SERVER (zombicito.duckdns.org:6969)
  The project root has  start_server.ps1 : run it on the server machine
  and it updates DuckDNS with that machine's public IP (so the address
  never depends on your home IP) and launches ZamnServer.exe. The server
  simulates matches with CPU bots, lets players hop in mid-match, and
  starts a new match automatically when one ends.
  NOTE: the router must forward UDP 6969 to the server machine.
  Windows Firewall will ask to allow ZamnServer.exe - allow it.

WEB PAGE (zombicito.duckdns.org)
  serve_web.ps1 (project root) serves the game page (web/index.html) with
  downloads and instructions over HTTP on its OWN port (7070), so it never
  clashes with the other port-forwarded apps on your network (port 80 on
  this router belongs to "juega"). start_server.ps1 launches it too.
  Router rules: UDP 6969 -> server PC (game) + TCP 7070 -> server PC (page).

CONTROLS (same on every PC)
  Move ..... Arrows or WASD          Fire ..... Z, Space or F
  Gamepad .. Left stick / D-pad      Fire ..... A or X
  Esc ...... pause (single player) / leave match (multiplayer)

THE MAP
  1.5x composite of Level 1 "Zombie Panic" (2112x1248). Every area is
  reachable - collision is auto-generated from the art, all gates and
  passages are open, and connectivity is machine-verified at 100%.

NETWORK NOTES
  - UDP port 6969 (LAN games and the public server)
  - Host/server simulates the match; clients send inputs and render
    synced snapshots 30 times per second
  - If a player disconnects, a CPU bot takes over their character

TECH
  - Native C (GCC), SDL2, winsock UDP, 480x270 pixel-art viewport
  - Original SNES sprite sheets auto-sliced from community rips
  - CPU bots: BFS pathfinding + target arbitration
  - Procedural retro SFX synthesized at runtime
  - Rebuild: gcc main.c -O2 -o ..\Zamn.exe -I <SDL2>\include -L <SDL2>\lib
             -lSDL2 -lws2_32 -mwindows
  - ZamnServer.exe: same source, -DSERVER_MODE (console build)
  - Self-test modes:
      Zamn.exe --shot menu|lobby|options|charsel|play|playteams out.png [frames]
      Zamn.exe --host-test <frames> out.png [2|4]     (headless host)
      Zamn.exe --join-test <frames> out.png <hostip>  (headless client)
      Zamn.exe --browse-test <frames> out.png         (lists LAN lobbies)
