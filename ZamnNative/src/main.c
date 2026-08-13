/*
 * ZOMBIES ATE MY NEIGHBORS — Native Edition
 * From-scratch native remake in C + SDL2 (no emulation).
 * One human per PC. MULTIPLAYER opens a LAN lobby (host or join by IP):
 * 4 teams of 2 or 2 teams of 2 — host simulates, clients sync over UDP,
 * CPU bots fill every empty slot. Camera follows YOUR character.
 */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#define SDL_MAIN_HANDLED
#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include "font8x8_basic.h"
#include "sprites.h"
#include "assets_embedded.h"

#define VIEW_W 480
#define VIEW_H 270
#define WIN_SCALE 3
#define MAP_W 2112
#define MAP_H 1248
#define TS 16
#define TW 132
#define TH 78

#define MAX_PLAYERS 8
#define MAX_ZOMBIES 32
#define MAX_BULLETS 128
#define MAX_VICTIMS 16
#define MAX_FX 16
#define MAX_MED 8
#define NET_PORT 6969
#define DEFAULT_SERVER "zombicito.duckdns.org"

typedef enum { MODE_SP, MODE_TEAMS } Mode;
typedef enum { CTRL_LOCAL, CTRL_NET, CTRL_BOT } CtrlType;

/* ---------- global SDL ---------- */
static SDL_Window *gWin;
static SDL_Renderer *gRen;
static SDL_Texture *texZeke, *texJulie, *texZombie, *texVict, *texItems, *texDoor, *texLevel;
static unsigned char gWalk[TW * TH];
static SDL_GameController *gPad;
static int gShotMode = 0;
static char gShotFile[260];
/* autopilot net test: 0 off, 1 host, 2 join */
static int gAuto = 0, gAutoFrames = 0, gAutoTeams = 4;
static char gAutoIp[40] = "127.0.0.1";

/* ---------- audio synth ---------- */
typedef struct { int active, wave; float fA, fB, dur, t, vol; unsigned rng; } Voice;
static Voice gVoices[10];
static SDL_AudioDeviceID gAudio;
static int gVolume = 7;
static float gMaster = 0.7f;

static void audio_cb(void *ud, Uint8 *stream, int len) {
    (void)ud;
    float *out = (float *)stream;
    int n = len / 4;
    static float phase[10];
    for (int i = 0; i < n; i++) out[i] = 0.f;
    for (int v = 0; v < 10; v++) {
        Voice *V = &gVoices[v];
        if (!V->active) continue;
        for (int i = 0; i < n; i++) {
            float k = V->t / V->dur;
            if (k >= 1.f) { V->active = 0; break; }
            float f = V->fA + (V->fB - V->fA) * k;
            float env = 1.f - k;
            float s;
            if (V->wave == 0) s = (fmodf(phase[v], 1.f) < 0.5f) ? 1.f : -1.f;
            else { V->rng = V->rng * 1103515245u + 12345u; s = ((V->rng >> 16 & 0x7fff) / 16383.5f) - 1.f; }
            out[i] += s * env * V->vol * gMaster * (gVolume / 10.f);
            phase[v] += f / 48000.f;
            V->t += 1.f / 48000.f;
        }
    }
    for (int i = 0; i < n; i++) { if (out[i] > 1) out[i] = 1; if (out[i] < -1) out[i] = -1; }
}
static void sfx(int wave, float fA, float fB, float dur, float vol) {
    if (!gAudio) return;
    SDL_LockAudioDevice(gAudio);
    for (int v = 0; v < 10; v++) if (!gVoices[v].active) {
        gVoices[v] = (Voice){1, wave, fA, fB, dur, 0.f, vol, 0xC0FFEE ^ (unsigned)v * 7919u};
        break;
    }
    SDL_UnlockAudioDevice(gAudio);
}
/* sound ids (shared with net clients via snapshot event ring) */
enum { SND_SHOOT, SND_HIT, SND_ZDIE, SND_RESCUE, SND_HURT, SND_EATEN, SND_MENU, SND_CONFIRM, SND_DOOR, SND_SPAWN, SND_STUN };
static void play_snd(int id) {
    switch (id) {
        case SND_SHOOT:   sfx(0, 900, 250, 0.08f, 0.22f); break;
        case SND_HIT:     sfx(1, 0, 0, 0.05f, 0.30f); break;
        case SND_ZDIE:    sfx(0, 300, 50, 0.30f, 0.35f); sfx(1, 0, 0, 0.15f, 0.2f); break;
        case SND_RESCUE:  sfx(0, 523, 523, 0.09f, 0.3f); sfx(0, 784, 784, 0.18f, 0.3f); sfx(0, 1047, 1568, 0.3f, 0.3f); break;
        case SND_HURT:    sfx(0, 120, 60, 0.2f, 0.4f); break;
        case SND_EATEN:   sfx(0, 160, 40, 0.4f, 0.4f); break;
        case SND_MENU:    sfx(0, 660, 660, 0.04f, 0.25f); break;
        case SND_CONFIRM: sfx(0, 880, 1320, 0.12f, 0.3f); break;
        case SND_DOOR:    sfx(0, 220, 480, 0.35f, 0.35f); break;
        case SND_SPAWN:   sfx(1, 0, 0, 0.10f, 0.10f); break;
        case SND_STUN:    sfx(0, 500, 180, 0.15f, 0.3f); break;
    }
}
/* host: play locally + queue for clients; everywhere else just play */
static struct { unsigned char seq, id; } gSndRing[8];
static unsigned char gSndSeq = 0;
static int gHosting = 0;
static void snd_event(int id) {
    play_snd(id);
    if (gHosting) {
        gSndSeq++;
        for (int i = 7; i > 0; i--) gSndRing[i] = gSndRing[i-1];
        gSndRing[0].seq = gSndSeq; gSndRing[0].id = (unsigned char)id;
    }
}

/* ---------- text ---------- */
static void draw_text(int x, int y, int sc, SDL_Color c, const char *s) {
    SDL_SetRenderDrawColor(gRen, c.r, c.g, c.b, 255);
    for (; *s; s++, x += 8 * sc) {
        unsigned ch = (unsigned char)*s;
        if (ch > 127) continue;
        for (int ry = 0; ry < 8; ry++) {
            unsigned bits = (unsigned char)font8x8_basic[ch][ry];
            for (int rx = 0; rx < 8; rx++) if (bits & (1u << rx)) {
                SDL_Rect r = { x + rx * sc, y + ry * sc, sc, sc };
                SDL_RenderFillRect(gRen, &r);
            }
        }
    }
}
static void draw_text_sh(int x, int y, int sc, SDL_Color c, const char *s) {
    draw_text(x + sc, y + sc, sc, (SDL_Color){10, 25, 10, 255}, s);
    draw_text(x, y, sc, c, s);
}
static int text_w(int sc, const char *s) { return (int)strlen(s) * 8 * sc; }
static void draw_text_c(int cx, int y, int sc, SDL_Color c, const char *s) { draw_text_sh(cx - text_w(sc, s) / 2, y, sc, c, s); }

/* ---------- assets ---------- */
static int near_rgb(unsigned char *p, int r, int g, int b, int tol) {
    return abs(p[0] - r) <= tol && abs(p[1] - g) <= tol && abs(p[2] - b) <= tol;
}
static SDL_Texture *load_sheet(const unsigned char *data, unsigned int len, int keyMode) {
    int w, h, comp;
    unsigned char *px = stbi_load_from_memory(data, (int)len, &w, &h, &comp, 4);
    if (!px) { SDL_Log("Failed to decode embedded asset"); exit(1); }
    if (keyMode) {
        unsigned char kr = px[0], kg = px[1], kb = px[2];
        for (int i = 0; i < w * h; i++) {
            unsigned char *p = px + i * 4;
            int key = (p[0] == kr && p[1] == kg && p[2] == kb);
            if (!key && keyMode == 2)
                key = near_rgb(p, 8, 176, 120, 26) || near_rgb(p, 8, 112, 80, 20);
            if (key) p[3] = 0;
        }
    }
    SDL_Surface *sf = SDL_CreateRGBSurfaceWithFormatFrom(px, w, h, 32, w * 4, SDL_PIXELFORMAT_RGBA32);
    SDL_Texture *t = SDL_CreateTextureFromSurface(gRen, sf);
    SDL_FreeSurface(sf);
    stbi_image_free(px);
    SDL_SetTextureBlendMode(t, SDL_BLENDMODE_BLEND);
    return t;
}

/* ---------- world ---------- */
static int walkable_px(float x, float y) {
    if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return 0;
    return gWalk[(int)(y / TS) * TW + (int)(x / TS)];
}
static int box_free(float x, float y, int hw, int hh) {
    return walkable_px(x - hw, y - hh) && walkable_px(x + hw, y - hh) &&
           walkable_px(x - hw, y + hh) && walkable_px(x + hw, y + hh);
}
static void nudge_walkable(float *x, float *y) {
    if (box_free(*x, *y + 4, 5, 3)) return;
    for (int r = 1; r < 12; r++) for (int a = 0; a < 16; a++) {
        float nx = *x + cosf(a * 0.3927f) * r * 12.f, ny = *y + sinf(a * 0.3927f) * r * 12.f;
        if (nx > 16 && ny > 16 && nx < MAP_W - 16 && ny < MAP_H - 16 && box_free(nx, ny + 4, 5, 3)) { *x = nx; *y = ny; return; }
    }
}

typedef struct {
    float x, y; int dir;
    float animT; int frame;
    int hp, lives; long score;
    float fireCd, hurtT, deadT, stunT;
    int charId, team;
    CtrlType ctrl;
    int alive, used;
    unsigned char netButtons; float netLastT;
    int botTarget; float botRepathT, botAvoidT, botAvX, botAvY, botLastX, botLastY, botStuckT;
    short botPath[160]; int botPathLen, botPathPos;
} Player;
typedef struct { float x, y; int st; float animT, hurtT; int frame, hp, dir; int used; } Zombie;
typedef struct { float x, y, vx, vy, ttl; int owner, used; } Bullet;
typedef struct { float x, y; int type, st; float animT; int frame; } Victim;
typedef struct { float x, y, t; int type; int used; } Fx;
typedef struct { float x, y, respawnT; int taken; } Medkit;
typedef struct { int rescues; long score; } Team;

static Mode gMode = MODE_SP;
static int gTeamCount = 4;
static Player gP[MAX_PLAYERS];
static int gNumPlayers = 1;
static int gLocalSlot = 0;
static Zombie gZ[MAX_ZOMBIES];
static Bullet gB[MAX_BULLETS];
static Victim gV[MAX_VICTIMS];
static int gNumVictims = MAX_VICTIMS;
static Fx gFx[MAX_FX];
static Medkit gMed[MAX_MED];
static Team gTeam[4];
static float gSpawnT, gElapsed;
static int gDoorOpen, gRescued, gEaten;
static float gDoorX = 480, gDoorY = 78;
static float gCamX, gCamY;
static float gMsgT; static char gMsg[40];

static const SDL_Color TEAMCOL[4] = {
    {110, 235, 70, 255}, {235, 70, 70, 255}, {90, 150, 255, 255}, {255, 220, 60, 255}
};
static const char *TEAMNAME[4] = { "GREEN", "RED", "BLUE", "YELLOW" };

static const struct { int x, y, type; } VSPOTS[MAX_VICTIMS] = {
    {200, 190, 0}, {700, 150, 3}, {620, 470, 2}, {1060, 420, 0}, {1250, 350, 2},
    {250, 700, 3}, {620, 700, 0}, {660, 300, 1}, {1000, 100, 1}, {1370, 480, 2},
    {1756, 420, 1}, {1566, 350, 2}, {1816, 100, 4}, {620, 1194, 3}, {250, 964, 0}, {620, 964, 4},
};
static const struct { int x, y; } TSPAWN[4] = {
    {340, 600}, {1384, 456}, {340, 1000}, {1576, 952}
};
static int team_spawn_idx(int team) { return gTeamCount == 2 ? (team ? 3 : 0) : team; }

static const Frame *vic_frames(int type, int *n) {
    switch (type) {
        case 0: *n = vic_cheer_N; return vic_cheer;
        case 1: *n = vic_dog_N; return vic_dog;
        case 2: *n = vic_soldier_N; return vic_soldier;
        case 3: *n = vic_kid_N; return vic_kid;
        default: *n = vic_tourist_N; return vic_tourist;
    }
}
static void add_fx(float x, float y, int type) {
    for (int i = 0; i < MAX_FX; i++) if (!gFx[i].used) { gFx[i] = (Fx){x, y, 0.f, type, 1}; return; }
}
static void msg(const char *s) { snprintf(gMsg, sizeof gMsg, "%s", s); gMsgT = 2.2f; }

/* ---------- networking ---------- */
#pragma pack(push, 1)
typedef struct { unsigned char type; } PkJoin;                         /* 1 client->host */
typedef struct {                                                        /* 2 host->client */
    unsigned char type, mode2teams, started, yourSlot;
    unsigned char kinds[MAX_PLAYERS];  /* 0 cpu, 1 host, 2+ client n */
    unsigned char team[MAX_PLAYERS], charId[MAX_PLAYERS];  /* starcraft-style lobby choices */
    unsigned char ready[MAX_PLAYERS], botEnabled[MAX_PLAYERS];
} PkLobby;
typedef struct { unsigned char type, slot, buttons, seq; } PkInput;     /* 3 client->host */
typedef struct { unsigned char type, slot, team, charId; } PkEdit;      /* 6 client->host lobby edit */
typedef struct {                                                        /* 4 host->client */
    unsigned char type, phase, teamCount, numPlayers;
    unsigned char rescued, eaten, numVictims, medTaken;
    short teamRescues[4]; long teamScore[4];
    struct { short x, y; unsigned char dir, frame, hp, alive, team, charId, stun, ctrlBot; } pl[MAX_PLAYERS];
    struct { short x, y; unsigned char st, frame, dir, used; } zb[MAX_ZOMBIES];
    struct { short x, y; unsigned char used; } bl[64];
    struct { unsigned char st, frame; } vc[MAX_VICTIMS];
    struct { short x, y, t100; unsigned char type, used; } fx[MAX_FX];
    struct { unsigned char seq, id; } snd[8];
    char msg[40]; unsigned char msgOn;
} PkSnap;
typedef struct {                                                        /* 5 host->LAN beacon */
    unsigned char type, mode2teams, started, filled, slots;
    char name[16];
} PkBeacon;
#pragma pack(pop)

static SOCKET gSock = INVALID_SOCKET;
static struct sockaddr_in gHostAddr;
static struct sockaddr_in gClientAddr[MAX_PLAYERS]; /* host: addr per slot */
static int gClientKnown[MAX_PLAYERS];
static unsigned char gKinds[MAX_PLAYERS];
static unsigned char gLobTeam[MAX_PLAYERS], gLobChar[MAX_PLAYERS];
static unsigned char gLobReady[MAX_PLAYERS], gBotEnabled[MAX_PLAYERS];
static int gNetStarted = 0, gNetPhase = 1;
static int gMySlot = 0;
static float gNetLastRx = 0, gNetTime = 0, gLobbyBcastT = 0, gJoinReqT = 0, gJoinStartT = 0;
static int gLobbyGot = 0;
static unsigned char gLastSndSeq = 0;
/* dedicated server mode (headless, all slots bots until humans join) */
static int gServerMode = 0;
static float gServerStartT = 0, gServerRestartT = 0;
static int gAutoConnect = 0;

/* public lobby browser: hosts announce via LAN broadcast, clients list them */
#define MAX_LOBBIES 8
typedef struct {
    unsigned int addr; unsigned short port;
    unsigned char started, filled, slots, mode2teams;
    char name[16];
    float lastSeen;
} LobbyEntry;
static LobbyEntry gLobList[MAX_LOBBIES];
static int gLobCount = 0, gLobSel = 0;
static float gBeaconT = 0;

static void net_close(void) {
    if (gSock != INVALID_SOCKET) { closesocket(gSock); gSock = INVALID_SOCKET; }
    gHosting = 0; gNetStarted = 0; gLobbyGot = 0; gNetPhase = 1;
    memset(gClientKnown, 0, sizeof gClientKnown);
}
static int net_host_open(void) {
    net_close();
    gSock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (gSock == INVALID_SOCKET) return 0;
    int on = 1;
    setsockopt(gSock, SOL_SOCKET, SO_BROADCAST, (const char *)&on, sizeof on);
    setsockopt(gSock, SOL_SOCKET, SO_REUSEADDR, (const char *)&on, sizeof on);
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET; a.sin_port = htons(NET_PORT); a.sin_addr.s_addr = INADDR_ANY;
    if (bind(gSock, (struct sockaddr *)&a, sizeof a) != 0) { net_close(); return 0; }
    u_long nb = 1; ioctlsocket(gSock, FIONBIO, &nb);
    memset(gKinds, 0, sizeof gKinds);
    for (int i = 0; i < MAX_PLAYERS; i++) {
        gLobTeam[i] = (unsigned char)(i / 2); gLobChar[i] = (unsigned char)(i & 1);
        gLobReady[i] = 1; gBotEnabled[i] = 1;
    }
    gLobReady[0] = 0; gBotEnabled[0] = 0;
    gKinds[0] = 1; gMySlot = 0; gHosting = 1; gNetPhase = 1;
    return 1;
}
static int net_browse_open(void) {
    net_close();
    gSock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (gSock == INVALID_SOCKET) return 0;
    int on = 1;
    setsockopt(gSock, SOL_SOCKET, SO_REUSEADDR, (const char *)&on, sizeof on);
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET; a.sin_port = htons(NET_PORT); a.sin_addr.s_addr = INADDR_ANY;
    if (bind(gSock, (struct sockaddr *)&a, sizeof a) != 0) {
        struct sockaddr_in ep = {0};
        ep.sin_family = AF_INET; ep.sin_port = 0; ep.sin_addr.s_addr = INADDR_ANY;
        if (bind(gSock, (struct sockaddr *)&ep, sizeof ep) != 0) { net_close(); return 0; }
    }
    u_long nb = 1; ioctlsocket(gSock, FIONBIO, &nb);
    return 1;
}
static int net_client_open(const char *host) {
    net_close();
    gSock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (gSock == INVALID_SOCKET) return 0;
    u_long nb = 1; ioctlsocket(gSock, FIONBIO, &nb);
    memset(&gHostAddr, 0, sizeof gHostAddr);
    gHostAddr.sin_family = AF_INET; gHostAddr.sin_port = htons(NET_PORT);
    unsigned long ip = inet_addr(host);
    if (ip == INADDR_NONE) {
        struct hostent *he = gethostbyname(host);
        if (!he || !he->h_addr_list[0]) { net_close(); return 0; }
        memcpy(&gHostAddr.sin_addr, he->h_addr_list[0], he->h_length);
    } else {
        gHostAddr.sin_addr.s_addr = ip;
    }
    gNetLastRx = gNetTime;
    return 1;
}
static void host_broadcast_lobby(void); /* fwd */
static int next_free_human_slot(void) {
    static const int pref4[8] = {0, 2, 4, 6, 1, 3, 5, 7};
    static const int pref2[4] = {0, 2, 1, 3};
    const int *pref = gTeamCount == 2 ? pref2 : pref4;
    int n = gTeamCount * 2;
    for (int i = 0; i < n; i++) if (gKinds[pref[i]] == 0 && !gBotEnabled[pref[i]]) return pref[i];
    for (int i = 0; i < n; i++) if (gKinds[pref[i]] == 0) return pref[i];
    return -1;
}
static void lobby_upsert(struct sockaddr_in *from, PkBeacon *b) {
    int i;
    for (i = 0; i < gLobCount; i++)
        if (gLobList[i].addr == from->sin_addr.s_addr && gLobList[i].port == from->sin_port) break;
    if (i == gLobCount) { if (gLobCount >= MAX_LOBBIES) return; gLobCount++; }
    gLobList[i].addr = from->sin_addr.s_addr; gLobList[i].port = from->sin_port;
    gLobList[i].started = b->started; gLobList[i].filled = b->filled;
    gLobList[i].slots = b->slots; gLobList[i].mode2teams = b->mode2teams;
    snprintf(gLobList[i].name, sizeof gLobList[i].name, "%s", b->name);
    gLobList[i].lastSeen = gNetTime;
}
static void lobby_prune(void) {
    for (int i = 0; i < gLobCount; i++) {
        if (gNetTime - gLobList[i].lastSeen > 2.5f) {
            for (int j = i; j < gLobCount - 1; j++) gLobList[j] = gLobList[j + 1];
            gLobCount--; i--;
        }
    }
    if (gLobSel >= gLobCount) gLobSel = gLobCount > 0 ? gLobCount - 1 : 0;
}
static void host_send_beacon(void) {
    PkBeacon b;
    memset(&b, 0, sizeof b);
    b.type = 5; b.mode2teams = (unsigned char)(gTeamCount == 2);
    b.started = (unsigned char)gNetStarted; b.slots = (unsigned char)(gTeamCount * 2);
    b.filled = 0;
    for (int i = 0; i < MAX_PLAYERS; i++) if (gKinds[i]) b.filled++;
    char host[16] = "ZAMN";
    gethostname(host, sizeof host);
    host[15] = 0;
    snprintf(b.name, sizeof b.name, "%s", host);
    struct sockaddr_in bc = {0};
    bc.sin_family = AF_INET; bc.sin_port = htons(NET_PORT);
    bc.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    sendto(gSock, (char *)&b, sizeof b, 0, (struct sockaddr *)&bc, sizeof bc);
}
static void host_send_lobby(struct sockaddr_in *to, int slot) {
    PkLobby p = {0};
    p.type = 2; p.mode2teams = gTeamCount == 2; p.started = (unsigned char)gNetStarted;
    p.yourSlot = (unsigned char)slot;
    memcpy(p.kinds, gKinds, sizeof p.kinds);
    memcpy(p.team, gLobTeam, sizeof p.team);
    memcpy(p.charId, gLobChar, sizeof p.charId);
    memcpy(p.ready, gLobReady, sizeof p.ready);
    memcpy(p.botEnabled, gBotEnabled, sizeof p.botEnabled);
    sendto(gSock, (char *)&p, sizeof p, 0, (struct sockaddr *)to, sizeof *to);
}
static void host_poll(void) {
    char buf[2048];
    struct sockaddr_in from; int flen = sizeof from;
    while (1) {
        int n = recvfrom(gSock, buf, sizeof buf, 0, (struct sockaddr *)&from, &flen);
        if (n <= 0) break;
        if (buf[0] == 1) { /* join request */
            int slot = -1;
            for (int i = 0; i < MAX_PLAYERS; i++)
                if (gClientKnown[i] && gClientAddr[i].sin_addr.s_addr == from.sin_addr.s_addr &&
                    gClientAddr[i].sin_port == from.sin_port) { slot = i; break; }
            if (slot < 0 && !gNetStarted) {
                slot = next_free_human_slot();
                if (slot >= 0) {
                    int clientNo = 2;
                    for (int i = 0; i < MAX_PLAYERS; i++) if (gKinds[i] >= 2) clientNo++;
                    gKinds[slot] = (unsigned char)clientNo;
                    gBotEnabled[slot] = 0; gLobReady[slot] = 0;
                    gClientAddr[slot] = from; gClientKnown[slot] = 1;
                    if (gNumPlayers > slot) gP[slot].netLastT = gNetTime;
                    if (gServerMode) printf("SERVER: PC %d joined\n", clientNo);
                }
            }
            if (slot < 0 && gNetStarted && gServerMode) {
                /* dedicated server: let players hop in mid-match */
                slot = next_free_human_slot();
                if (slot >= 0) {
                    int clientNo = 2;
                    for (int i = 0; i < MAX_PLAYERS; i++) if (gKinds[i] >= 2) clientNo++;
                    gKinds[slot] = (unsigned char)clientNo;
                    gBotEnabled[slot] = 0; gLobReady[slot] = 0;
                    gClientAddr[slot] = from; gClientKnown[slot] = 1;
                    gP[slot].ctrl = CTRL_NET; gP[slot].alive = 1; gP[slot].hp = 5;
                    gP[slot].hurtT = 2.f;
                    gP[slot].x = (float)TSPAWN[team_spawn_idx(gP[slot].team)].x;
                    gP[slot].y = (float)TSPAWN[team_spawn_idx(gP[slot].team)].y;
                    nudge_walkable(&gP[slot].x, &gP[slot].y);
                    gP[slot].netLastT = gNetTime;
                    printf("SERVER: PC %d joined mid-match\n", clientNo);
                }
            }
            if (slot >= 0) host_send_lobby(&from, slot);
        } else if (buf[0] == 3 && n >= (int)sizeof(PkInput)) {
            PkInput *pi = (PkInput *)buf;
            if (pi->slot < MAX_PLAYERS && gClientKnown[pi->slot]) {
                gP[pi->slot].netButtons = pi->buttons;
                gP[pi->slot].netLastT = gNetTime;
            }
        } else if (buf[0] == 6 && n >= (int)sizeof(PkEdit)) {
            /* lobby edit: change team/char of a slot (own slot, or bots if host) */
            PkEdit *pe = (PkEdit *)buf;
            int who = -1;
            for (int i = 0; i < MAX_PLAYERS; i++)
                if (gClientKnown[i] && gClientAddr[i].sin_addr.s_addr == from.sin_addr.s_addr &&
                    gClientAddr[i].sin_port == from.sin_port) { who = i; break; }
            if (who < 0 || pe->slot >= MAX_PLAYERS) continue;
            int isMine = who == pe->slot;
            int isHostBotEdit = who == 0 && gKinds[pe->slot] == 0;
            if ((isMine || isHostBotEdit) && pe->team < gTeamCount && pe->charId < 2) {
                gLobTeam[pe->slot] = pe->team;
                gLobChar[pe->slot] = pe->charId;
                host_broadcast_lobby();
            }
        }
    }
}
static void host_broadcast_lobby(void) {
    for (int i = 0; i < MAX_PLAYERS; i++)
        if (gClientKnown[i]) host_send_lobby(&gClientAddr[i], i);
}
static void host_send_snapshot(void) {
    static PkSnap s;
    memset(&s, 0, sizeof s);
    s.type = 4; s.phase = (unsigned char)gNetPhase;
    s.teamCount = (unsigned char)gTeamCount; s.numPlayers = (unsigned char)gNumPlayers;
    s.rescued = (unsigned char)gRescued; s.eaten = (unsigned char)gEaten;
    s.numVictims = (unsigned char)gNumVictims;
    for (int m = 0; m < MAX_MED; m++) if (gMed[m].taken) s.medTaken |= 1 << m;
    for (int t = 0; t < 4; t++) { s.teamRescues[t] = (short)gTeam[t].rescues; s.teamScore[t] = gTeam[t].score; }
    for (int i = 0; i < gNumPlayers; i++) {
        s.pl[i].x = (short)gP[i].x; s.pl[i].y = (short)gP[i].y;
        s.pl[i].dir = (unsigned char)gP[i].dir; s.pl[i].frame = (unsigned char)gP[i].frame;
        s.pl[i].hp = (unsigned char)(gP[i].hp < 0 ? 0 : gP[i].hp); s.pl[i].alive = (unsigned char)gP[i].alive;
        s.pl[i].team = (unsigned char)gP[i].team; s.pl[i].charId = (unsigned char)gP[i].charId;
        s.pl[i].stun = gP[i].stunT > 0 ? 1 : 0;
        s.pl[i].ctrlBot = gP[i].ctrl == CTRL_BOT ? 1 : 0;
    }
    for (int i = 0; i < MAX_ZOMBIES; i++) {
        s.zb[i].x = (short)gZ[i].x; s.zb[i].y = (short)gZ[i].y;
        s.zb[i].st = (unsigned char)gZ[i].st; s.zb[i].frame = (unsigned char)gZ[i].frame;
        s.zb[i].dir = (unsigned char)gZ[i].dir; s.zb[i].used = (unsigned char)gZ[i].used;
    }
    int bn = 0;
    for (int i = 0; i < MAX_BULLETS && bn < 64; i++) if (gB[i].used) {
        s.bl[bn].x = (short)gB[i].x; s.bl[bn].y = (short)gB[i].y; s.bl[bn].used = 1; bn++;
    }
    for (int v = 0; v < gNumVictims; v++) { s.vc[v].st = (unsigned char)gV[v].st; s.vc[v].frame = (unsigned char)gV[v].frame; }
    for (int i = 0; i < MAX_FX; i++) {
        s.fx[i].x = (short)gFx[i].x; s.fx[i].y = (short)gFx[i].y;
        s.fx[i].t100 = (short)(gFx[i].t * 100); s.fx[i].type = (unsigned char)gFx[i].type;
        s.fx[i].used = (unsigned char)gFx[i].used;
    }
    memcpy(s.snd, gSndRing, sizeof s.snd);
    memcpy(s.msg, gMsg, sizeof s.msg);
    s.msgOn = gMsgT > 0 ? 1 : 0;
    for (int i = 0; i < MAX_PLAYERS; i++)
        if (gClientKnown[i]) sendto(gSock, (char *)&s, sizeof s, 0, (struct sockaddr *)&gClientAddr[i], sizeof gClientAddr[i]);
}
static void client_apply_snapshot(PkSnap *s) {
    gNetPhase = s->phase;
    gTeamCount = s->teamCount; gNumPlayers = s->numPlayers;
    gRescued = s->rescued; gEaten = s->eaten; gNumVictims = s->numVictims;
    for (int m = 0; m < MAX_MED; m++) gMed[m].taken = (s->medTaken >> m) & 1;
    for (int t = 0; t < 4; t++) { gTeam[t].rescues = s->teamRescues[t]; gTeam[t].score = s->teamScore[t]; }
    for (int i = 0; i < gNumPlayers && i < MAX_PLAYERS; i++) {
        gP[i].used = 1;
        gP[i].x = s->pl[i].x; gP[i].y = s->pl[i].y;
        gP[i].dir = s->pl[i].dir; gP[i].frame = s->pl[i].frame;
        gP[i].hp = s->pl[i].hp; gP[i].alive = s->pl[i].alive;
        gP[i].team = s->pl[i].team; gP[i].charId = s->pl[i].charId;
        gP[i].stunT = s->pl[i].stun ? 1.f : 0.f;
        gP[i].hurtT = 0;
        gP[i].ctrl = s->pl[i].ctrlBot ? CTRL_BOT : CTRL_NET;
    }
    for (int i = 0; i < MAX_ZOMBIES; i++) {
        gZ[i].x = s->zb[i].x; gZ[i].y = s->zb[i].y;
        gZ[i].st = s->zb[i].st; gZ[i].frame = s->zb[i].frame;
        gZ[i].dir = s->zb[i].dir; gZ[i].used = s->zb[i].used;
        gZ[i].hurtT = 0;
    }
    memset(gB, 0, sizeof gB);
    for (int i = 0; i < 64; i++) if (s->bl[i].used) { gB[i].x = s->bl[i].x; gB[i].y = s->bl[i].y; gB[i].used = 1; }
    for (int v = 0; v < gNumVictims && v < MAX_VICTIMS; v++) { gV[v].st = s->vc[v].st; gV[v].frame = s->vc[v].frame; }
    for (int i = 0; i < MAX_FX; i++) {
        gFx[i].x = s->fx[i].x; gFx[i].y = s->fx[i].y; gFx[i].t = s->fx[i].t100 / 100.f;
        gFx[i].type = s->fx[i].type; gFx[i].used = s->fx[i].used;
    }
    for (int i = 7; i >= 0; i--) {
        unsigned char sq = s->snd[i].seq;
        if (sq && (unsigned char)(sq - gLastSndSeq) <= 128 && sq != gLastSndSeq) {
            /* play sounds newer than what we've heard */
            if ((unsigned char)(sq - gLastSndSeq) < 8) play_snd(s->snd[i].id);
        }
    }
    if (s->snd[0].seq) gLastSndSeq = s->snd[0].seq;
    if (s->msgOn) { memcpy(gMsg, s->msg, sizeof gMsg); gMsg[39] = 0; gMsgT = 0.5f; }
    else gMsgT = 0;
}
static int client_poll(void) {
    char buf[4096];
    struct sockaddr_in from; int flen = sizeof from;
    int got = 0;
    while (1) {
        int n = recvfrom(gSock, buf, sizeof buf, 0, (struct sockaddr *)&from, &flen);
        if (n <= 0) break;
        if (buf[0] == 2 && n >= (int)sizeof(PkLobby)) {
            PkLobby *p = (PkLobby *)buf;
            gTeamCount = p->mode2teams ? 2 : 4;
            gMySlot = p->yourSlot;
            memcpy(gKinds, p->kinds, sizeof gKinds);
            memcpy(gLobTeam, p->team, sizeof gLobTeam);
            memcpy(gLobChar, p->charId, sizeof gLobChar);
            memcpy(gLobReady, p->ready, sizeof gLobReady);
            memcpy(gBotEnabled, p->botEnabled, sizeof gBotEnabled);
            gLobbyGot = 1;
            if (p->started) gNetStarted = 1;
            gNetLastRx = gNetTime; got = 1;
        } else if (buf[0] == 4 && n >= (int)sizeof(PkSnap)) {
            client_apply_snapshot((PkSnap *)buf);
            gNetStarted = 1;
            gNetLastRx = gNetTime; got = 1;
        } else if (buf[0] == 5 && n >= (int)sizeof(PkBeacon)) {
            lobby_upsert(&from, (PkBeacon *)buf);
            gNetLastRx = gNetTime;
        }
    }
    return got;
}

/* ---------- game setup ---------- */
static void setup_victims_medkits(void) {
    for (int i = 0; i < gNumVictims; i++) {
        gV[i] = (Victim){(float)VSPOTS[i].x, (float)VSPOTS[i].y, VSPOTS[i].type, 0, (float)(i * 37 % 10) / 10.f, 0};
        nudge_walkable(&gV[i].x, &gV[i].y);
    }
    for (int i = gNumVictims; i < MAX_VICTIMS; i++) gV[i].st = 3;
    gMed[0] = (Medkit){170, 420, 0, 0}; gMed[1] = (Medkit){1300, 480, 0, 0}; gMed[2] = (Medkit){900, 640, 0, 0};
    gMed[3] = (Medkit){1600, 900, 0, 0}; gMed[4] = (Medkit){1526, 160, 0, 0}; gMed[5] = (Medkit){400, 1000, 0, 0};
    gMed[6] = (Medkit){700, 900, 0, 0}; gMed[7] = (Medkit){1750, 320, 0, 0};
    for (int i = 0; i < MAX_MED; i++) nudge_walkable(&gMed[i].x, &gMed[i].y);
}
static void game_reset(Mode mode, int charSel) {
    memset(gZ, 0, sizeof gZ); memset(gB, 0, sizeof gB); memset(gFx, 0, sizeof gFx);
    memset(gP, 0, sizeof gP);
    memset(gTeam, 0, sizeof gTeam);
    gMode = mode;
    gNumPlayers = mode == MODE_SP ? 1 : gTeamCount * 2;
    gNumVictims = mode == MODE_SP ? 12 : MAX_VICTIMS;
    for (int i = 0; i < gNumPlayers; i++) {
        Player *P = &gP[i];
        P->used = (i == gMySlot || gKinds[i] >= 2 || gBotEnabled[i]) ? 1 : 0;
        P->alive = P->used;
        P->hp = 5; P->lives = mode == MODE_SP ? 3 : 99;
        P->botTarget = -1;
        if (mode == MODE_TEAMS) {
            P->team = gLobTeam[i] % gTeamCount;
            P->charId = gLobChar[i] < 2 ? gLobChar[i] : (unsigned char)(i & 1);
            if (i == gMySlot) P->ctrl = CTRL_LOCAL;
            else if (gKinds[i] >= 2) P->ctrl = CTRL_NET;
            else P->ctrl = CTRL_BOT;
            P->x = (float)TSPAWN[team_spawn_idx(P->team)].x + (i & 1) * 24;
            P->y = (float)TSPAWN[team_spawn_idx(P->team)].y;
            P->netLastT = gNetTime;
        } else {
            P->team = 0; P->charId = charSel; P->ctrl = CTRL_LOCAL;
            P->x = 340.f; P->y = 600.f;
        }
        nudge_walkable(&P->x, &P->y);
    }
    setup_victims_medkits();
    gSpawnT = 1.2f; gElapsed = 0; gDoorOpen = 0; gRescued = 0; gEaten = 0;
    gMsg[0] = 0; gMsgT = 0;
    gNetPhase = 1;
    msg(mode == MODE_TEAMS ? "MOST RESCUES WINS!" : "RESCUE THE NEIGHBORS!");
}
static void client_setup(void) { /* client mirrors world for rendering */
    memset(gZ, 0, sizeof gZ); memset(gB, 0, sizeof gB); memset(gFx, 0, sizeof gFx);
    memset(gP, 0, sizeof gP); memset(gTeam, 0, sizeof gTeam);
    gMode = MODE_TEAMS;
    gNumPlayers = gTeamCount * 2;
    gNumVictims = MAX_VICTIMS;
    setup_victims_medkits();
    gLocalSlot = gMySlot;
    gMsg[0] = 0; gMsgT = 0;
}

/* ---------- zombies / bullets / bots (host-side sim) ---------- */
static short gEdgeTiles[TW * TH];
static int gEdgeCount;
static void init_world(void) {
    gEdgeCount = 0;
    for (int ty = 1; ty < TH - 1; ty++) for (int tx = 1; tx < TW - 1; tx++) {
        if (!gWalk[ty * TW + tx]) continue;
        int isEdge = 0;
        for (int d = 0; d < 4 && !isEdge; d++) {
            int nx = tx + (d == 0 ? 1 : d == 1 ? -1 : 0);
            int ny = ty + (d == 2 ? 1 : d == 3 ? -1 : 0);
            if (!gWalk[ny * TW + nx]) isEdge = 1;
        }
        if (isEdge) gEdgeTiles[gEdgeCount++] = (short)(ty * TW + tx);
    }
}
static void spawn_zombie(void) {
    int used = 0;
    for (int i = 0; i < MAX_ZOMBIES; i++) used += gZ[i].used;
    int cap = gMode == MODE_TEAMS ? (4 + 3 * gNumPlayers) : 20;
    if (cap > MAX_ZOMBIES) cap = MAX_ZOMBIES;
    if (used >= cap) return;
    for (int tries = 0; tries < 40; tries++) {
        int tx, ty;
        if (tries < 24 && gEdgeCount > 0) {
            int t = gEdgeTiles[rand() % gEdgeCount];
            tx = t % TW; ty = t / TW;
        } else {
            tx = rand() % TW; ty = rand() % TH;
        }
        if (!gWalk[ty * TW + tx]) continue;
        float x = tx * TS + 8, y = ty * TS + 8;
        int tooClose = 0, nearEnough = 0;
        for (int i = 0; i < gNumPlayers; i++) {
            float dx = x - gP[i].x, dy = y - gP[i].y, d = dx * dx + dy * dy;
            if (d < 130 * 130) tooClose = 1;
            if (d < 420 * 420) nearEnough = 1;
        }
        for (int v = 0; v < gNumVictims; v++) {
            if (gV[v].st != 0) continue;
            float dx = x - gV[v].x, dy = y - gV[v].y;
            if (dx * dx + dy * dy < 48 * 48) { tooClose = 1; break; }
        }
        if (tooClose || !nearEnough) continue;
        for (int i = 0; i < MAX_ZOMBIES; i++) if (!gZ[i].used) {
            gZ[i] = (Zombie){x, y, 0, 0.f, 0.f, 0, 3, 0, 1};
            snd_event(SND_SPAWN);
            return;
        }
    }
}
static void spawn_bullet(Player *P, float dx, float dy) {
    float L = sqrtf(dx * dx + dy * dy);
    if (L < 0.1f) { dx = 0; dy = 1; L = 1; }
    for (int b = 0; b < MAX_BULLETS; b++) if (!gB[b].used) {
        gB[b] = (Bullet){P->x + dx / L * 8, P->y - 4 + dy / L * 8, dx / L * 250.f, dy / L * 250.f, 0.75f, (int)(P - gP), 1};
        break;
    }
    snd_event(SND_SHOOT);
}

static int bfs_path(int sx, int sy, int gx, int gy, short *out, int maxLen) {
    static short cameFrom[TW * TH];
    static short queue[TW * TH];
    static unsigned char seen[TW * TH];
    if (sx < 0 || sy < 0 || sx >= TW || sy >= TH || gx < 0 || gy < 0 || gx >= TW || gy >= TH) return 0;
    int *fix[2][2] = { {&sx, &sy}, {&gx, &gy} };
    for (int f = 0; f < 2; f++) {
        int *px = fix[f][0], *py = fix[f][1];
        if (gWalk[*py * TW + *px]) continue;
        int found = 0;
        for (int r = 1; r < 5 && !found; r++) for (int dy = -r; dy <= r && !found; dy++) for (int dx = -r; dx <= r; dx++) {
            int nx = *px + dx, ny = *py + dy;
            if (nx >= 0 && ny >= 0 && nx < TW && ny < TH && gWalk[ny * TW + nx]) { *px = nx; *py = ny; found = 1; break; }
        }
        if (!found) return 0;
    }
    memset(seen, 0, sizeof seen);
    int head = 0, tail = 0;
    int start = sy * TW + sx, goal = gy * TW + gx;
    queue[tail++] = (short)start; seen[start] = 1; cameFrom[start] = -1;
    static const int DX[4] = {1, -1, 0, 0}, DY[4] = {0, 0, 1, -1};
    while (head < tail) {
        int cur = queue[head++];
        if (cur == goal) break;
        int cx = cur % TW, cy = cur / TW;
        for (int d = 0; d < 4; d++) {
            int nx = cx + DX[d], ny = cy + DY[d];
            if (nx < 0 || ny < 0 || nx >= TW || ny >= TH) continue;
            int ni = ny * TW + nx;
            if (seen[ni] || !gWalk[ni]) continue;
            seen[ni] = 1; cameFrom[ni] = (short)cur;
            queue[tail++] = (short)ni;
        }
    }
    if (!seen[goal]) return 0;
    static short tmp[TW * TH];
    int n = 0;
    for (int cur = goal; cur != -1 && n < TW * TH; cur = cameFrom[cur]) tmp[n++] = (short)cur;
    int len = n - 1 < maxLen ? n - 1 : maxLen;
    for (int i = 0; i < len; i++) out[i] = tmp[n - 2 - i];
    return len;
}

static void bot_input(Player *P, float dt, float *ix, float *iy, int *fire, float *fdx, float *fdy) {
    *ix = *iy = 0; *fire = 0; *fdx = 0; *fdy = 1;
    P->botRepathT -= dt;
    int retarget = 0;
    if (P->botTarget >= 0 && gV[P->botTarget].st != 0) {
        P->botTarget = -1; retarget = 1;
        P->botAvoidT = 0.9f; P->botAvX = 0; P->botAvY = 0;
    }
    if (P->botTarget < 0 || P->botRepathT <= 0) {
        float best = 1e18f; int bi = -1;
        for (int v = 0; v < gNumVictims; v++) {
            if (gV[v].st != 0) continue;
            float dx = gV[v].x - P->x, dy = gV[v].y - P->y;
            float d = dx * dx + dy * dy;
            for (int o = 0; o < gNumPlayers; o++)
                if (o != (int)(P - gP) && gP[o].used && gP[o].team == P->team && gP[o].botTarget == v) d *= 3.f;
            if (d < best) { best = d; bi = v; }
        }
        if (bi != P->botTarget) retarget = 1;
        P->botTarget = bi;
    }
    float tx, ty; int haveTarget = 0;
    if (P->botTarget >= 0) { tx = gV[P->botTarget].x; ty = gV[P->botTarget].y; haveTarget = 1; }
    else {
        float best = 1e18f; tx = P->x; ty = P->y;
        for (int i = 0; i < MAX_ZOMBIES; i++) {
            if (!gZ[i].used || gZ[i].st != 1) continue;
            float dx = gZ[i].x - P->x, dy = gZ[i].y - P->y, d = dx * dx + dy * dy;
            if (d < best) { best = d; tx = gZ[i].x; ty = gZ[i].y; haveTarget = 1; }
        }
    }
    if (haveTarget && (retarget || P->botRepathT <= 0)) {
        P->botRepathT = 0.7f + (float)(rand() % 30) / 100.f;
        P->botPathLen = bfs_path((int)(P->x / TS), (int)((P->y + 4) / TS), (int)(tx / TS), (int)((ty + 4) / TS),
                                 P->botPath, 160);
        P->botPathPos = 0;
    }
    float wx = tx, wy = ty;
    while (P->botPathPos < P->botPathLen) {
        int t = P->botPath[P->botPathPos];
        wx = (t % TW) * TS + 8.f; wy = (t / TW) * TS + 8.f;
        float ddx = wx - P->x, ddy = wy - P->y;
        if (ddx * ddx + ddy * ddy < 6 * 6) { P->botPathPos++; continue; }
        break;
    }
    if (P->botPathPos >= P->botPathLen) { wx = tx; wy = ty; }
    P->botStuckT += dt;
    if (P->botStuckT > 0.5f) {
        float mv = fabsf(P->x - P->botLastX) + fabsf(P->y - P->botLastY);
        if (mv < 5.f) {
            P->botAvoidT = 0.5f;
            float a = (float)(rand() % 628) / 100.f;
            P->botAvX = cosf(a); P->botAvY = sinf(a);
            P->botRepathT = 0;
        }
        P->botLastX = P->x; P->botLastY = P->y; P->botStuckT = 0;
    }
    if (P->botAvoidT > 0) {
        P->botAvoidT -= dt;
        *ix = P->botAvX; *iy = P->botAvY;
    } else if (haveTarget) {
        float dx = wx - P->x, dy = wy - P->y;
        float L = sqrtf(dx * dx + dy * dy);
        if (L > 3) { *ix = dx / L; *iy = dy / L; }
    }
    float best = 90.f * 90.f; int zi = -1;
    for (int i = 0; i < MAX_ZOMBIES; i++) {
        if (!gZ[i].used || gZ[i].st != 1) continue;
        float dx = gZ[i].x - P->x, dy = gZ[i].y - P->y, d = dx * dx + dy * dy;
        if (d < best) { best = d; zi = i; }
    }
    if (zi >= 0) { *fire = 1; *fdx = gZ[zi].x - P->x; *fdy = gZ[zi].y - P->y; }
}

/* merged local input: arrows + WASD + Z/Space/F + gamepad 0 */
static void read_local_input(float *ix, float *iy, int *fire) {
    const Uint8 *k = SDL_GetKeyboardState(NULL);
    *ix = (float)((k[SDL_SCANCODE_RIGHT] || k[SDL_SCANCODE_D]) - (k[SDL_SCANCODE_LEFT] || k[SDL_SCANCODE_A]));
    *iy = (float)((k[SDL_SCANCODE_DOWN] || k[SDL_SCANCODE_S]) - (k[SDL_SCANCODE_UP] || k[SDL_SCANCODE_W]));
    *fire = k[SDL_SCANCODE_Z] || k[SDL_SCANCODE_SPACE] || k[SDL_SCANCODE_F];
    if (gPad) {
        float ax = SDL_GameControllerGetAxis(gPad, SDL_CONTROLLER_AXIS_LEFTX) / 32767.f;
        float ay = SDL_GameControllerGetAxis(gPad, SDL_CONTROLLER_AXIS_LEFTY) / 32767.f;
        if (fabsf(ax) > 0.28f) *ix = ax;
        if (fabsf(ay) > 0.28f) *iy = ay;
        if (SDL_GameControllerGetButton(gPad, SDL_CONTROLLER_BUTTON_DPAD_LEFT)) *ix = -1;
        if (SDL_GameControllerGetButton(gPad, SDL_CONTROLLER_BUTTON_DPAD_RIGHT)) *ix = 1;
        if (SDL_GameControllerGetButton(gPad, SDL_CONTROLLER_BUTTON_DPAD_UP)) *iy = -1;
        if (SDL_GameControllerGetButton(gPad, SDL_CONTROLLER_BUTTON_DPAD_DOWN)) *iy = 1;
        if (SDL_GameControllerGetButton(gPad, SDL_CONTROLLER_BUTTON_A) ||
            SDL_GameControllerGetButton(gPad, SDL_CONTROLLER_BUTTON_X)) *fire = 1;
    }
}
static unsigned char pack_buttons(float ix, float iy, int fire) {
    unsigned char b = 0;
    if (iy < -0.2f) b |= 1;
    if (iy > 0.2f) b |= 2;
    if (ix < -0.2f) b |= 4;
    if (ix > 0.2f) b |= 8;
    if (fire) b |= 16;
    return b;
}

/* ---------- update (host / SP authoritative sim) ---------- */
static void update_game(float dt) {
    gElapsed += dt;
    if (gMsgT > 0) gMsgT -= dt;

    for (int m = 0; m < MAX_MED; m++) if (gMed[m].taken && gMode == MODE_TEAMS && gMed[m].respawnT > 0) {
        gMed[m].respawnT -= dt;
        if (gMed[m].respawnT <= 0) gMed[m].taken = 0;
    }

    for (int pi = 0; pi < gNumPlayers; pi++) {
        Player *P = &gP[pi];
        if (!P->used) continue;
        /* net timeout -> bot takeover */
        if (P->ctrl == CTRL_NET && gNetTime - P->netLastT > 4.f) P->ctrl = CTRL_BOT;
        if (!P->alive) {
            P->deadT -= dt;
            if (P->deadT <= 0 && P->lives > 0) {
                P->alive = 1; P->hp = 5; P->hurtT = 2.f;
                if (gMode == MODE_TEAMS) {
                    P->x = (float)TSPAWN[team_spawn_idx(P->team)].x; P->y = (float)TSPAWN[team_spawn_idx(P->team)].y;
                    nudge_walkable(&P->x, &P->y);
                }
            }
            continue;
        }
        float ix = 0, iy = 0, fdx = 0, fdy = 0;
        int fire = 0, aimExplicit = 0;
        if (P->stunT > 0) { P->stunT -= dt; }
        else if (P->ctrl == CTRL_LOCAL) read_local_input(&ix, &iy, &fire);
        else if (P->ctrl == CTRL_NET) {
            unsigned char b = P->netButtons;
            iy = (float)(((b >> 1) & 1) - (b & 1));
            ix = (float)(((b >> 3) & 1) - ((b >> 2) & 1));
            fire = (b >> 4) & 1;
        } else { bot_input(P, dt, &ix, &iy, &fire, &fdx, &fdy); aimExplicit = 1; }
        float L2 = ix * ix + iy * iy;
        if (L2 > 1.f) { float L = sqrtf(L2); ix /= L; iy /= L; }
        float sp = P->ctrl == CTRL_BOT ? 74.f : 88.f;
        float nx = P->x + ix * sp * dt, ny = P->y + iy * sp * dt;
        if (box_free(nx, P->y + 4, 5, 3)) P->x = nx;
        if (box_free(P->x, ny + 4, 5, 3)) P->y = ny;
        if (fabsf(ix) > 0.05f || fabsf(iy) > 0.05f) {
            P->animT += dt * 9.f;
            if (fabsf(ix) > fabsf(iy) * 0.99f) P->dir = ix > 0 ? 3 : 1;
            else P->dir = iy > 0 ? 0 : 2;
        } else P->animT = 0;
        P->frame = (int)P->animT % 5;
        if (P->fireCd > 0) P->fireCd -= dt;
        if (P->hurtT > 0) P->hurtT -= dt;
        if (fire && P->fireCd <= 0 && P->stunT <= 0) {
            P->fireCd = 0.22f;
            if (!aimExplicit) {
                if (fabsf(ix) > 0.05f || fabsf(iy) > 0.05f) { fdx = ix; fdy = iy; }
                else { fdx = P->dir == 3 ? 1.f : P->dir == 1 ? -1.f : 0.f; fdy = P->dir == 0 ? 1.f : P->dir == 2 ? -1.f : 0.f; }
            }
            spawn_bullet(P, fdx, fdy);
        }
        for (int v = 0; v < gNumVictims; v++) {
            if (gV[v].st != 0) continue;
            float dx = gV[v].x - P->x, dy = gV[v].y - P->y;
            if (dx * dx + dy * dy < 14 * 14) {
                gV[v].st = 1;
                gRescued++; P->score += 1000;
                add_fx(gV[v].x, gV[v].y, 1);
                snd_event(SND_RESCUE);
                char b[40];
                if (gMode == MODE_TEAMS) {
                    gTeam[P->team].rescues++; gTeam[P->team].score += 1000;
                    snprintf(b, sizeof b, "TEAM %s SAVED ONE!", TEAMNAME[P->team]);
                } else
                    snprintf(b, sizeof b, "SAVED! %d LEFT", gNumVictims - gRescued - gEaten);
                msg(b);
            }
        }
        for (int m = 0; m < MAX_MED; m++) {
            if (gMed[m].taken) continue;
            float dx = gMed[m].x - P->x, dy = gMed[m].y - P->y;
            if (dx * dx + dy * dy < 12 * 12 && P->hp < 5) {
                gMed[m].taken = 1; gMed[m].respawnT = 25.f; P->hp = 5; snd_event(SND_CONFIRM);
            }
        }
    }

    if (gMode != MODE_TEAMS && !gDoorOpen && gRescued + gEaten == gNumVictims && gRescued > 0) {
        gDoorOpen = 1; snd_event(SND_DOOR); msg("THE EXIT DOOR IS OPEN!");
    }

    gSpawnT -= dt;
    float interval = 2.8f - gElapsed * 0.02f;
    if (interval < 1.15f) interval = 1.15f;
    if (gMode == MODE_TEAMS) interval *= gTeamCount == 2 ? 0.8f : 0.55f;
    if (gSpawnT <= 0) { gSpawnT = interval; spawn_zombie(); }

    for (int i = 0; i < MAX_ZOMBIES; i++) {
        Zombie *Z = &gZ[i];
        if (!Z->used) continue;
        Z->animT += dt;
        if (Z->st == 0) {
            Z->frame = (int)(Z->animT * 5.f);
            if (Z->frame >= zom_rise_N) { Z->st = 1; Z->animT = 0; Z->frame = 0; }
            continue;
        }
        if (Z->st == 2) {
            Z->frame = (int)(Z->animT * 9.f);
            if (Z->frame >= zom_die_N) Z->used = 0;
            continue;
        }
        if (Z->hurtT > 0) Z->hurtT -= dt;
        float tx = 0, ty = 0, best = 1e18f; int found = 0;
        for (int p = 0; p < gNumPlayers; p++) {
            if (!gP[p].used || !gP[p].alive) continue;
            float dx = gP[p].x - Z->x, dy = gP[p].y - Z->y, d = dx * dx + dy * dy;
            if (d < best) { best = d; tx = gP[p].x; ty = gP[p].y; found = 1; }
        }
        for (int v = 0; v < gNumVictims; v++) {
            if (gV[v].st != 0) continue;
            float dx = gV[v].x - Z->x, dy = gV[v].y - Z->y, d = (dx * dx + dy * dy) * 3.2f;
            if (d < best) { best = d; tx = gV[v].x; ty = gV[v].y; found = 1; }
        }
        if (!found) continue;
        float dx = tx - Z->x, dy = ty - Z->y;
        float L = sqrtf(dx * dx + dy * dy);
        if (L > 1) { dx /= L; dy /= L; }
        float sp = 34.f + fminf(18.f, gElapsed * 0.22f);
        float nx = Z->x + dx * sp * dt, ny = Z->y + dy * sp * dt;
        int movedX = 0;
        if (box_free(nx, Z->y + 4, 5, 3)) { Z->x = nx; movedX = 1; }
        if (box_free(Z->x, ny + 4, 5, 3)) Z->y = ny;
        else if (!movedX) {
            if (box_free(Z->x + (dx > 0 ? 1.f : -1.f) * sp * dt, Z->y + 4, 5, 3)) Z->x += (dx > 0 ? 1.f : -1.f) * sp * dt;
        }
        Z->dir = fabsf(dx) > fabsf(dy) ? (dx > 0 ? 3 : 1) : (dy > 0 ? 0 : 2);
        Z->frame = (int)(Z->animT * 6.f) % 4;
        for (int v = 0; v < gNumVictims; v++) {
            if (gV[v].st != 0) continue;
            float vx = gV[v].x - Z->x, vy = gV[v].y - Z->y;
            if (vx * vx + vy * vy < 11 * 11) {
                gV[v].st = 2; gEaten++;
                add_fx(gV[v].x, gV[v].y, 2);
                snd_event(SND_EATEN);
                msg("A NEIGHBOR WAS EATEN!");
            }
        }
        for (int p = 0; p < gNumPlayers; p++) {
            Player *P = &gP[p];
            if (!P->used || !P->alive || P->hurtT > 0) continue;
            float px = P->x - Z->x, py = P->y - Z->y;
            if (px * px + py * py < 11 * 11) {
                P->hp--; P->hurtT = 1.0f; snd_event(SND_HURT);
                if (P->hp <= 0) {
                    P->lives--; P->alive = 0; P->deadT = gMode == MODE_TEAMS ? 3.0f : 1.5f;
                    add_fx(P->x, P->y, 2);
                    if (P->lives <= 0) P->deadT = 1e9f;
                }
            }
        }
    }

    for (int b = 0; b < MAX_BULLETS; b++) {
        Bullet *B = &gB[b];
        if (!B->used) continue;
        B->ttl -= dt;
        B->x += B->vx * dt; B->y += B->vy * dt;
        if (B->ttl <= 0 || !walkable_px(B->x, B->y)) { add_fx(B->x, B->y, 0); B->used = 0; continue; }
        for (int i = 0; i < MAX_ZOMBIES && B->used; i++) {
            Zombie *Z = &gZ[i];
            if (!Z->used || Z->st != 1) continue;
            float dx = Z->x - B->x, dy = (Z->y - 8) - B->y;
            if (dx * dx + dy * dy < 10 * 10) {
                B->used = 0; add_fx(B->x, B->y, 0);
                Z->hp--; Z->hurtT = 0.1f; snd_event(SND_HIT);
                if (Z->hp <= 0) {
                    Z->st = 2; Z->animT = 0; snd_event(SND_ZDIE);
                    Player *O = &gP[B->owner];
                    O->score += 150;
                    if (gMode == MODE_TEAMS) gTeam[O->team].score += 150;
                }
            }
        }
        if (gMode == MODE_TEAMS && B->used) {
            for (int p = 0; p < gNumPlayers && B->used; p++) {
                Player *T = &gP[p];
                if (!T->used || !T->alive || p == B->owner) continue;
                if (T->team == gP[B->owner].team) continue;
                if (T->stunT > 0) continue;
                float dx = T->x - B->x, dy = (T->y - 6) - B->y;
                if (dx * dx + dy * dy < 9 * 9) {
                    B->used = 0; add_fx(B->x, B->y, 0);
                    T->stunT = 0.7f;
                    float kx = B->vx * 0.03f, ky = B->vy * 0.03f;
                    if (box_free(T->x + kx, T->y + 4, 5, 3)) T->x += kx;
                    if (box_free(T->x, T->y + ky + 4, 5, 3)) T->y += ky;
                    snd_event(SND_STUN);
                }
            }
        }
    }

    for (int i = 0; i < MAX_FX; i++) if (gFx[i].used) {
        gFx[i].t += dt;
        float lim = gFx[i].type == 1 ? 1.1f : 0.4f;
        if (gFx[i].t > lim) gFx[i].used = 0;
    }
    for (int v = 0; v < gNumVictims; v++) if (gV[v].st == 0) {
        gV[v].animT += dt * 5.f;
        int n; vic_frames(gV[v].type, &n);
        gV[v].frame = (int)gV[v].animT % n;
    }
}

/* camera: always centered on the local player's character */
static void update_camera(void) {
    int s = gLocalSlot;
    if (s >= gNumPlayers || !gP[s].used) s = 0;
    gCamX = gP[s].x - VIEW_W / 2.f; gCamY = gP[s].y - VIEW_H / 2.f;
    if (gCamX < 0) gCamX = 0; if (gCamY < 0) gCamY = 0;
    if (gCamX > MAP_W - VIEW_W) gCamX = MAP_W - VIEW_W;
    if (gCamY > MAP_H - VIEW_H) gCamY = MAP_H - VIEW_H;
}

/* ---------- rendering ---------- */
static void blit(SDL_Texture *t, const Frame *f, float wx, float wy, int flip, int anchorBottom) {
    SDL_Rect src = { f->x, f->y, f->w, f->h };
    SDL_Rect dst = { (int)(wx - f->w / 2.f - gCamX), (int)(wy - (anchorBottom ? f->h : f->h / 2.f) - gCamY), f->w, f->h };
    SDL_RenderCopyEx(gRen, t, &src, &dst, 0, NULL, flip ? SDL_FLIP_HORIZONTAL : SDL_FLIP_NONE);
}
static void render_player(Player *P, int slotIdx) {
    if (!P->used || !P->alive) return;
    if (P->hurtT > 0 && ((int)(P->hurtT * 12) & 1)) return;
    SDL_Texture *t = P->charId == 0 ? texZeke : texJulie;
    const Frame *set; int setN, flip = 0;
    if (P->charId == 0) {
        switch (P->dir) {
            case 0: set = zeke_down; setN = zeke_down_N; break;
            case 2: set = zeke_up; setN = zeke_up_N; break;
            case 3: set = zeke_left; setN = zeke_left_N; flip = 1; break;
            default: set = zeke_left; setN = zeke_left_N; break;
        }
    } else {
        switch (P->dir) {
            case 0: set = julie_down; setN = julie_down_N; break;
            case 2: set = julie_up; setN = julie_up_N; break;
            case 3: set = julie_right; setN = julie_right_N; break;
            default: set = julie_left; setN = julie_left_N; break;
        }
    }
    if (P->stunT > 0) SDL_SetTextureColorMod(t, 130, 160, 255);
    blit(t, &set[P->frame % setN], P->x, P->y + 8, flip, 1);
    SDL_SetTextureColorMod(t, 255, 255, 255);
    if (gMode == MODE_TEAMS) {
        SDL_Color c = TEAMCOL[P->team];
        int sx = (int)(P->x - gCamX), sy = (int)(P->y - gCamY);
        SDL_SetRenderDrawColor(gRen, c.r, c.g, c.b, 255);
        SDL_Rect mk = { sx - 2, sy - 34, 5, 3 };
        SDL_RenderFillRect(gRen, &mk);
        SDL_Rect mk2 = { sx - 1, sy - 31, 3, 2 };
        SDL_RenderFillRect(gRen, &mk2);
        SDL_SetRenderDrawColor(gRen, 20, 20, 20, 255);
        SDL_Rect hb = { sx - 8, sy - 28, 16, 3 };
        SDL_RenderFillRect(gRen, &hb);
        SDL_SetRenderDrawColor(gRen, P->hp > 2 ? 80 : 230, P->hp > 2 ? 220 : 60, 60, 255);
        SDL_Rect hf = { sx - 7, sy - 27, 14 * (P->hp > 5 ? 5 : P->hp) / 5, 1 };
        SDL_RenderFillRect(gRen, &hf);
        if (slotIdx == gLocalSlot) draw_text(sx - 14, sy - 38, 1, (SDL_Color){255, 255, 255, 255}, "YOU");
        else if (P->ctrl == CTRL_BOT) draw_text(sx + 6, sy - 36, 1, (SDL_Color){160, 160, 160, 255}, "C");
    }
}
static void render_game(void) {
    update_camera();
    SDL_Rect src = { (int)gCamX, (int)gCamY, VIEW_W, VIEW_H };
    SDL_Rect dst = { 0, 0, VIEW_W, VIEW_H };
    SDL_RenderCopy(gRen, texLevel, &src, &dst);

    if (gMode != MODE_TEAMS)
        blit(texDoor, gDoorOpen ? &door_open[0] : &door_closed[0], gDoorX, gDoorY + 38, 0, 1);

    for (int m = 0; m < MAX_MED; m++) if (!gMed[m].taken)
        blit(texItems, &icon_medkit[0], gMed[m].x, gMed[m].y + 8, 0, 1);
    for (int v = 0; v < gNumVictims; v++) {
        if (gV[v].st != 0) continue;
        int n; const Frame *fs = vic_frames(gV[v].type, &n);
        blit(texVict, &fs[gV[v].frame % n], gV[v].x, gV[v].y + 8, 0, 1);
    }
    for (int i = 0; i < MAX_ZOMBIES; i++) {
        Zombie *Z = &gZ[i];
        if (!Z->used) continue;
        if (Z->st == 0) {
            int f = Z->frame < zom_rise_N ? Z->frame : zom_rise_N - 1;
            blit(texZombie, &zom_rise[f], Z->x, Z->y + 8, 0, 1);
        } else if (Z->st == 2) {
            int f = Z->frame < zom_die_N ? Z->frame : zom_die_N - 1;
            blit(texZombie, &zom_die[f], Z->x, Z->y + 8, 0, 1);
        } else {
            const Frame *set; int flip = 0;
            switch (Z->dir) {
                case 0: set = zom_down; break;
                case 2: set = zom_up; break;
                case 3: set = zom_right; break;
                default: set = zom_right; flip = 1; break;
            }
            if (Z->hurtT > 0) SDL_SetTextureColorMod(texZombie, 255, 120, 120);
            blit(texZombie, &set[Z->frame % 4], Z->x, Z->y + 8, flip, 1);
            SDL_SetTextureColorMod(texZombie, 255, 255, 255);
        }
    }
    for (int p = 0; p < gNumPlayers; p++) render_player(&gP[p], p);
    for (int b = 0; b < MAX_BULLETS; b++) if (gB[b].used) {
        SDL_SetRenderDrawColor(gRen, 90, 160, 255, 255);
        SDL_Rect r = { (int)(gB[b].x - gCamX) - 1, (int)(gB[b].y - gCamY) - 1, 3, 3 };
        SDL_RenderFillRect(gRen, &r);
        SDL_SetRenderDrawColor(gRen, 220, 240, 255, 255);
        SDL_Rect r2 = { (int)(gB[b].x - gCamX), (int)(gB[b].y - gCamY), 1, 1 };
        SDL_RenderFillRect(gRen, &r2);
    }
    for (int i = 0; i < MAX_FX; i++) if (gFx[i].used) {
        Fx *F = &gFx[i];
        if (F->type == 1) {
            int f = (int)(F->t * 3.f); if (f > 2) f = 2;
            blit(texVict, &fx_angel[f], F->x, F->y + 8 - F->t * 22.f, 0, 1);
        } else {
            int f = (int)(F->t * 8.f); if (f > 2) f = 2;
            if (F->type == 2) SDL_SetTextureColorMod(texVict, 255, 80, 80);
            blit(texVict, &fx_sparkle[f], F->x, F->y, 0, 0);
            SDL_SetTextureColorMod(texVict, 255, 255, 255);
        }
    }
    /* HUD */
    if (gMode == MODE_TEAMS) {
        int pw = gTeamCount == 2 ? 200 : 118;
        for (int t = 0; t < gTeamCount; t++) {
            int hx = 6 + t * (pw + 2);
            SDL_Color c = TEAMCOL[t];
            SDL_SetRenderDrawBlendMode(gRen, SDL_BLENDMODE_BLEND);
            SDL_SetRenderDrawColor(gRen, 0, 0, 0, 160);
            SDL_Rect bg = { hx - 2, 3, pw - 4, 12 };
            SDL_RenderFillRect(gRen, &bg);
            char buf[40];
            long ds = gTeam[t].score > 9999 ? 9999 : gTeam[t].score;
            snprintf(buf, sizeof buf, "%s %d %04ld", TEAMNAME[t], gTeam[t].rescues, ds);
            draw_text(hx, 5, 1, c, buf);
        }
        char buf[40];
        int left = gNumVictims - gRescued - gEaten;
        snprintf(buf, sizeof buf, "NEIGHBORS LEFT %d", left);
        draw_text_c(VIEW_W / 2, 18, 1, (SDL_Color){255, 230, 120, 255}, buf);
    } else {
        Player *P = &gP[0];
        char buf[48];
        snprintf(buf, sizeof buf, "%s %06ld", P->charId == 0 ? "ZEKE" : "JULIE", P->score);
        draw_text_sh(6, 5, 1, (SDL_Color){120, 255, 120, 255}, buf);
        for (int i = 0; i < 5; i++) {
            SDL_SetRenderDrawColor(gRen, i < P->hp ? 60 : 30, i < P->hp ? 190 : 40, i < P->hp ? 255 : 50, 255);
            SDL_Rect r = { 6 + i * 8, 15, 6, 5 };
            SDL_RenderFillRect(gRen, &r);
        }
        snprintf(buf, sizeof buf, "x%d", P->lives);
        draw_text_sh(50, 14, 1, (SDL_Color){255, 255, 255, 255}, buf);
        int left = gNumVictims - gRescued - gEaten;
        snprintf(buf, sizeof buf, "NEIGHBORS %d", left);
        draw_text_c(VIEW_W / 2, 5, 1, (SDL_Color){255, 230, 120, 255}, buf);
    }
    if (gMsgT > 0 && gMsg[0])
        draw_text_c(VIEW_W / 2, VIEW_H - 18, 1, (SDL_Color){255, 255, 255, 255}, gMsg);
}

/* ---------- menus ---------- */
static float gMenuT = 0;
static void render_spiral(void) {
    SDL_SetRenderDrawColor(gRen, 12, 2, 16, 255);
    SDL_RenderClear(gRen);
    float cx = VIEW_W / 2.f, cy = VIEW_H / 2.f + 10;
    for (float r = 4; r < 300; r += 0.5f) {
        float a = r * 0.10f - gMenuT * 1.5f;
        float x = cx + cosf(a) * r, y = cy + sinf(a) * r * 0.62f;
        int bright = 150 + (int)(60 * sinf(r * 0.05f));
        SDL_SetRenderDrawColor(gRen, bright, 20, 30, 255);
        SDL_Rect q = { (int)x - 3, (int)y - 2, 7, 5 };
        SDL_RenderFillRect(gRen, &q);
    }
}
static const char *MENU_ITEMS[3] = { "SINGLE PLAYER", "MULTIPLAYER", "OPTIONS" };
static int gMenuIdx = 0;
static float gZomWalkT = 0;
static void menu_cursor(int cx, int y, const char *label) {
    int f = (int)(gZomWalkT * 6) % 4;
    Frame fr = zom_right[f];
    SDL_Rect src = { fr.x, fr.y, fr.w, fr.h };
    SDL_Rect dst = { cx - text_w(2, label) / 2 - 34, y - 10, fr.w, fr.h };
    SDL_RenderCopy(gRen, texZombie, &src, &dst);
}
static void render_menu(void) {
    render_spiral();
    int pulse = ((int)(gMenuT * 2.5f) % 4) < 2;
    SDL_Color red = pulse ? (SDL_Color){255, 70, 85, 255} : (SDL_Color){215, 45, 60, 255};
    draw_text_c(VIEW_W / 2 + 2, 22 + 2, 3, (SDL_Color){4, 12, 4, 255}, "ZOMBIES");
    draw_text_c(VIEW_W / 2, 22, 3, (SDL_Color){110, 235, 70, 255}, "ZOMBIES");
    draw_text_c(VIEW_W / 2 + 2, 48 + 2, 2, (SDL_Color){40, 6, 10, 255}, "ATE MY");
    draw_text_c(VIEW_W / 2, 48, 2, red, "ATE MY");
    draw_text_c(VIEW_W / 2 + 2, 70 + 2, 3, (SDL_Color){4, 12, 4, 255}, "NEIGHBORS");
    draw_text_c(VIEW_W / 2, 70, 3, (SDL_Color){110, 235, 70, 255}, "NEIGHBORS");
    draw_text_c(VIEW_W / 2, 102, 1, (SDL_Color){230, 210, 255, 255}, "NATIVE EDITION - LAN + ONLINE SERVER");
    for (int i = 0; i < 3; i++) {
        SDL_Color c = i == gMenuIdx ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255};
        int y = 134 + i * 24;
        draw_text_c(VIEW_W / 2 + 1, y + 1, 2, (SDL_Color){15, 25, 15, 255}, MENU_ITEMS[i]);
        draw_text_c(VIEW_W / 2, y, 2, c, MENU_ITEMS[i]);
        if (i == gMenuIdx) menu_cursor(VIEW_W / 2, y, MENU_ITEMS[i]);
    }
    draw_text_c(VIEW_W / 2, VIEW_H - 52, 1, (SDL_Color){150, 140, 160, 255}, "ARROWS SELECT   ENTER CONFIRM   ESC QUIT");

    /* lawn strip with tombstones and wandering zombies */
    SDL_Rect grass = { 0, VIEW_H - 28, VIEW_W, 28 };
    SDL_SetRenderDrawColor(gRen, 16, 38, 13, 255);
    SDL_RenderFillRect(gRen, &grass);
    SDL_SetRenderDrawColor(gRen, 10, 26, 9, 255);
    for (int x = 0; x < VIEW_W; x += 7) {
        SDL_Rect blade = { x, VIEW_H - 28 + (x / 5) % 5, 2, 3 };
        SDL_RenderFillRect(gRen, &blade);
    }
    int tombX[2] = { 40, VIEW_W - 70 };
    for (int t = 0; t < 2; t++) {
        SDL_SetRenderDrawColor(gRen, 78, 84, 92, 255);
        SDL_Rect tb = { tombX[t], VIEW_H - 30, 22, 30 };
        SDL_RenderFillRect(gRen, &tb);
        SDL_SetRenderDrawColor(gRen, 58, 63, 70, 255);
        SDL_Rect tb2 = { tombX[t] + 2, VIEW_H - 32, 18, 6 };
        SDL_RenderFillRect(gRen, &tb2);
        draw_text_c(tombX[t] + 11, VIEW_H - 20, 1, (SDL_Color){22, 24, 28, 255}, "RIP");
    }
    for (int z = 0; z < 3; z++) {
        float spd = 24.f + z * 8.f;
        float x = fmodf(gMenuT * spd + z * (VIEW_W + 40) / 3.f, VIEW_W + 40.f) - 20.f;
        if (x > VIEW_W) continue;
        int f = (int)(gZomWalkT * 6) % 4;
        Frame fr = zom_right[f];
        SDL_Rect src = { fr.x, fr.y, fr.w, fr.h };
        SDL_Rect dst = { (int)x, VIEW_H - 28 - fr.h + 4, fr.w, fr.h };
        SDL_RenderCopy(gRen, texZombie, &src, &dst);
    }
}

/* lobby */
static int gLobStage = 0;   /* 0 setup, 1 hosting, 2 joining */
static int gLobRow = 0;     /* setup rows: 0 mode, 1 host, 2 join ip, 3 browse */
static int gLobSelRow = 0;  /* starcraft table row selection (hosting/joined) */
static char gLobIp[48] = DEFAULT_SERVER;
static void menu_cursor_sc(int cx, int y, int sc, const char *label) {
    int f = (int)(gZomWalkT * 6) % 4;
    Frame fr = zom_right[f];
    SDL_Rect src = { fr.x, fr.y, fr.w, fr.h };
    SDL_Rect dst = { cx - text_w(sc, label) / 2 - 34, y - 10, fr.w, fr.h };
    SDL_RenderCopy(gRen, texZombie, &src, &dst);
}
static void render_lobby(void) {
    render_spiral();
    draw_text_c(VIEW_W / 2, 14, 2, (SDL_Color){110, 235, 70, 255}, "MULTIPLAYER LOBBY");
    char b[64];
    if (gLobStage == 0) {
        snprintf(b, sizeof b, "< %s >", gTeamCount == 4 ? "4 TEAMS OF 2" : "2 TEAMS OF 2");
        SDL_Color c0 = gLobRow == 0 ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255};
        draw_text_c(VIEW_W / 2, 58, 2, c0, b);
        SDL_Color c1 = gLobRow == 1 ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255};
        draw_text_c(VIEW_W / 2, 90, 2, c1, "HOST GAME");
        if (gLobRow == 1) menu_cursor(VIEW_W / 2, 90, "HOST GAME");
        SDL_Color c2 = gLobRow == 2 ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255};
        snprintf(b, sizeof b, "JOIN: %s_", gLobIp);
        int jsc = strlen(gLobIp) > 22 ? 1 : 2;
        draw_text_c(VIEW_W / 2, 122, jsc, c2, b);
        if (gLobRow == 2) menu_cursor_sc(VIEW_W / 2, 122, jsc, b);
        SDL_Color c3 = gLobRow == 3 ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255};
        draw_text_c(VIEW_W / 2, 154, 2, c3, "BROWSE GAMES");
        if (gLobRow == 3) menu_cursor(VIEW_W / 2, 154, "BROWSE GAMES");
        draw_text_c(VIEW_W / 2, 184, 1, (SDL_Color){230, 210, 255, 255}, "ONE PLAYER PER PC - CPU BOTS FILL EMPTY SLOTS");
        draw_text_c(VIEW_W / 2, 198, 1, (SDL_Color){230, 210, 255, 255}, "DEFAULT SERVER: zombicito.duckdns.org - OR BROWSE YOUR LAN");
        draw_text_c(VIEW_W / 2, VIEW_H - 22, 1, (SDL_Color){150, 140, 160, 255}, "ARROWS MOVE   LEFT/RIGHT MODE   ENTER CONFIRM   ESC BACK");
    } else if (gLobStage == 3) {
        draw_text_c(VIEW_W / 2, 14, 2, (SDL_Color){110, 235, 70, 255}, "PUBLIC GAMES ON YOUR LAN");
        if (gLobCount == 0) {
            draw_text_c(VIEW_W / 2, 96, 1, (SDL_Color){200, 190, 210, 255}, "SEARCHING FOR GAMES...");
        } else {
            for (int i = 0; i < gLobCount && i < 8; i++) {
                LobbyEntry *e = &gLobList[i];
                snprintf(b, sizeof b, "%s  %s  %d/%d  %s", e->name,
                         e->mode2teams ? "2 TEAMS" : "4 TEAMS", e->filled, e->slots,
                         e->started ? "IN GAME" : "WAITING");
                SDL_Color c = i == gLobSel ? (SDL_Color){255, 255, 120, 255}
                            : e->started ? (SDL_Color){110, 110, 110, 255} : (SDL_Color){220, 215, 230, 255};
                draw_text_c(VIEW_W / 2, 58 + i * 18, 1, c, b);
                if (i == gLobSel) menu_cursor(VIEW_W / 2, 58 + i * 18, b);
            }
        }
        draw_text_c(VIEW_W / 2, VIEW_H - 22, 1, (SDL_Color){150, 140, 160, 255}, "UP/DOWN SELECT   ENTER JOIN   ESC BACK");
    } else {
        int n = gTeamCount * 2;
        char hdr[40];
        snprintf(hdr, sizeof hdr, "SLOT  PLAYER %s      TEAM     CHAR", gTeamCount == 2 ? "     " : "");
        draw_text_c(VIEW_W / 2, 30, 1, (SDL_Color){170, 160, 185, 255}, hdr);        for (int i = 0; i < n; i++) {
            int sy = 46 + i * 16;
            const char *who = gBotEnabled[i] ? "CPU" : "";
            char pcbuf[12];
            if (gKinds[i] == 1) who = gLobStage == 1 ? "YOU" : "HOST";
            else if (gKinds[i] >= 2) {
                if (gLobStage == 2 && i == gMySlot) who = "YOU";
                else { snprintf(pcbuf, sizeof pcbuf, "PC %d", gKinds[i]); who = pcbuf; }
            }
            SDL_Color rowc = i == gLobSelRow ? (SDL_Color){255, 255, 120, 255}
                         : i == gMySlot ? (SDL_Color){230, 255, 190, 255}
                         : gKinds[i] ? (SDL_Color){220, 215, 230, 255} : (SDL_Color){140, 135, 155, 255};
            if (i == gLobSelRow) menu_cursor(14, sy + 4, "x");
            char tag[8];
            snprintf(tag, sizeof tag, "%d", i + 1);
            draw_text(20, sy, 1, rowc, tag);
            draw_text(40, sy, 1, rowc, who);
            SDL_Color tc = TEAMCOL[gLobTeam[i] % 4];
            draw_text(148, sy, 1, rowc, TEAMNAME[gLobTeam[i] % 4]);
            draw_text(206, sy, 1, i == gLobRow ? tc : rowc, gLobChar[i] == 0 ? "ZEKE" : "JULIE");
            const Frame *f = gLobChar[i] == 0 ? &zeke_down[0] : &julie_down[0];
            SDL_Texture *tex = gLobChar[i] == 0 ? texZeke : texJulie;
            SDL_Rect srcr = { f->x, f->y, f->w, f->h };
            SDL_Rect dstr = { 252, sy - 12, f->w, f->h };
            SDL_RenderCopy(gRen, tex, &srcr, &dstr);
        }
        if (gLobStage == 1) {
            draw_text_c(VIEW_W / 2, VIEW_H - 30, 1, (SDL_Color){255, 255, 120, 255}, "ENTER: START   L/R: TEAM   C: CHAR");
            char ipb[64];
            char host[64] = "?";
            gethostname(host, sizeof host);
            struct hostent *he = gethostbyname(host);
            if (he && he->h_addr_list[0])
                snprintf(ipb, sizeof ipb, "YOUR LAN IP: %s - PORT 6969", inet_ntoa(*(struct in_addr *)he->h_addr_list[0]));
            else snprintf(ipb, sizeof ipb, "YOUR PC NAME: %s", host);
            draw_text_c(VIEW_W / 2, VIEW_H - 18, 1, (SDL_Color){230, 210, 255, 255}, ipb);
        } else {
            draw_text_c(VIEW_W / 2, VIEW_H - 30, 1, (SDL_Color){230, 210, 255, 255}, "L/R: TEAM   C: CHAR   (HOST PICKS BOTS)");
            draw_text_c(VIEW_W / 2, VIEW_H - 18, 1, (SDL_Color){255, 255, 120, 255}, "WAITING FOR HOST TO START...");
        }
        (void)n;
    }
}

static int gOptIdx = 0, gFullscreen = 0, gSmooth = 0;
static void apply_filter(void) {
    SDL_ScaleMode m = gSmooth ? SDL_ScaleModeLinear : SDL_ScaleModeNearest;
    SDL_SetTextureScaleMode(texZeke, m); SDL_SetTextureScaleMode(texJulie, m);
    SDL_SetTextureScaleMode(texZombie, m); SDL_SetTextureScaleMode(texVict, m);
    SDL_SetTextureScaleMode(texItems, m); SDL_SetTextureScaleMode(texDoor, m);
    SDL_SetTextureScaleMode(texLevel, m);
}
static void render_options(void) {
    render_spiral();
    draw_text_c(VIEW_W / 2, 30, 3, (SDL_Color){110, 235, 70, 255}, "OPTIONS");
    char r0[64], r1[64], r2[64];
    snprintf(r0, sizeof r0, "FULLSCREEN  %s", gFullscreen ? "ON" : "OFF");
    snprintf(r1, sizeof r1, "FILTER  %s", gSmooth ? "SMOOTH" : "CRISP");
    snprintf(r2, sizeof r2, "SFX VOLUME  %d", gVolume);
    const char *rows[4] = { r0, r1, r2, "BACK" };
    for (int i = 0; i < 4; i++) {
        SDL_Color c = i == gOptIdx ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255};
        draw_text_c(VIEW_W / 2, 90 + i * 26, 2, c, rows[i]);
    }
    draw_text_c(VIEW_W / 2, VIEW_H - 22, 1, (SDL_Color){150, 140, 160, 255}, "LEFT/RIGHT CHANGE   ESC BACK");
}

static int gSelIdx = 0;
static void render_charsel(void) {
    render_spiral();
    draw_text_c(VIEW_W / 2, 22, 2, (SDL_Color){110, 235, 70, 255}, "CHOOSE YOUR HERO");
    for (int c = 0; c < 2; c++) {
        int px = VIEW_W / 2 + (c == 0 ? -90 : 90);
        int sel = gSelIdx == c;
        SDL_SetRenderDrawColor(gRen, sel ? 255 : 70, sel ? 240 : 40, sel ? 120 : 90, 255);
        SDL_Rect box = { px - 46, 48, 92, 150 };
        SDL_RenderDrawRect(gRen, &box);
        SDL_Rect box2 = { px - 45, 49, 90, 148 };
        if (sel) SDL_RenderDrawRect(gRen, &box2);
        const Frame *f = c == 0 ? &zeke_down[0] : &julie_down[0];
        SDL_Texture *t = c == 0 ? texZeke : texJulie;
        SDL_Rect src = { f->x, f->y, f->w, f->h };
        int s = 3;
        SDL_Rect dst = { px - f->w * s / 2, 66, f->w * s, f->h * s };
        SDL_RenderCopy(gRen, t, &src, &dst);
        draw_text_c(px, 172, 2, sel ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255}, c == 0 ? "ZEKE" : "JULIE");
    }
    draw_text_c(VIEW_W / 2, VIEW_H - 34, 1, (SDL_Color){230, 210, 255, 255}, "MOVE: ARROWS/WASD   FIRE: Z SPACE OR F");
    draw_text_c(VIEW_W / 2, VIEW_H - 22, 1, (SDL_Color){150, 140, 160, 255}, "ENTER CONFIRM   ESC BACK");
}

static void render_endcard(int win) {
    render_spiral();
    if (gMode == MODE_TEAMS) {
        int order[4] = {0, 1, 2, 3};
        for (int i = 0; i < gTeamCount; i++) for (int j = i + 1; j < gTeamCount; j++) {
            int a = order[i], bb = order[j];
            if (gTeam[bb].rescues > gTeam[a].rescues ||
                (gTeam[bb].rescues == gTeam[a].rescues && gTeam[bb].score > gTeam[a].score)) {
                order[i] = bb; order[j] = a;
            }
        }
        char b[64];
        snprintf(b, sizeof b, "TEAM %s WINS!", TEAMNAME[order[0]]);
        draw_text_c(VIEW_W / 2, 42, 3, TEAMCOL[order[0]], b);
        for (int i = 0; i < gTeamCount; i++) {
            int t = order[i];
            snprintf(b, sizeof b, "%d. %s  RESCUES %d  SCORE %06ld", i + 1, TEAMNAME[t], gTeam[t].rescues, gTeam[t].score);
            draw_text_c(VIEW_W / 2, 92 + i * 22, 1, TEAMCOL[t], b);
        }
        snprintf(b, sizeof b, "NEIGHBORS EATEN BY ZOMBIES: %d", gEaten);
        draw_text_c(VIEW_W / 2, 196, 1, (SDL_Color){200, 190, 210, 255}, b);
    } else if (win) {
        draw_text_c(VIEW_W / 2, 60, 3, (SDL_Color){110, 235, 70, 255}, "LEVEL CLEAR!");
        char b[64];
        snprintf(b, sizeof b, "NEIGHBORS SAVED: %d / %d", gRescued, gNumVictims);
        draw_text_c(VIEW_W / 2, 110, 2, (SDL_Color){255, 255, 255, 255}, b);
        snprintf(b, sizeof b, "SCORE %06ld", gP[0].score);
        draw_text_c(VIEW_W / 2, 140, 2, (SDL_Color){255, 230, 120, 255}, b);
    } else {
        draw_text_c(VIEW_W / 2, 60, 3, (SDL_Color){235, 60, 70, 255}, "GAME OVER");
        draw_text_c(VIEW_W / 2, 110, 2, (SDL_Color){255, 255, 255, 255}, "THE ZOMBIES WON...");
    }
    draw_text_c(VIEW_W / 2, VIEW_H - 40, 1, (SDL_Color){230, 210, 255, 255}, "ENTER: BACK TO MENU");
}

/* ---------- main ---------- */
typedef enum { ST_MENU, ST_LOBBY, ST_OPTIONS, ST_CHARSEL, ST_PLAY, ST_PAUSE, ST_WIN, ST_GAMEOVER } State;

static void save_frame_png(const char *file) {
    SDL_Texture *rt = SDL_CreateTexture(gRen, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_TARGET, VIEW_W, VIEW_H);
    SDL_SetRenderTarget(gRen, rt);
    /* re-render the current state into the target */
    extern void rerender_current(void);
    rerender_current();
    unsigned char *pix = malloc(VIEW_W * VIEW_H * 4);
    SDL_RenderReadPixels(gRen, NULL, SDL_PIXELFORMAT_RGBA32, pix, VIEW_W * 4);
    stbi_write_png(file, VIEW_W, VIEW_H, 4, pix, VIEW_W * 4);
    free(pix);
    SDL_SetRenderTarget(gRen, NULL);
    SDL_DestroyTexture(rt);
    printf("frame saved: %s\n", file);
}
static State gSt = ST_MENU;
void rerender_current(void) {
    switch (gSt) {
        case ST_MENU: render_menu(); break;
        case ST_LOBBY: render_lobby(); break;
        case ST_OPTIONS: render_options(); break;
        case ST_CHARSEL: render_charsel(); break;
        case ST_WIN: render_endcard(1); break;
        case ST_GAMEOVER: render_endcard(0); break;
        default: render_game(); break;
    }
}

int main(int argc, char **argv) {
    SDL_SetMainReady();
    int shotFrames = 0;
    const char *shotState = NULL;
    for (int i = 1; i < argc; i++) {        if (!strcmp(argv[i], "--shot") && i + 2 < argc) {
            gShotMode = 1; shotState = argv[i + 1];
            snprintf(gShotFile, sizeof gShotFile, "%s", argv[i + 2]);
            if (i + 3 < argc) shotFrames = atoi(argv[i + 3]);
        }
        if (!strcmp(argv[i], "--host-test") && i + 2 < argc) {
            gAuto = 1; gAutoFrames = atoi(argv[i + 1]);
            snprintf(gShotFile, sizeof gShotFile, "%s", argv[i + 2]);
            if (i + 3 < argc) gAutoTeams = atoi(argv[i + 3]) == 2 ? 2 : 4;
        }
        if (!strcmp(argv[i], "--join-test") && i + 3 < argc) {
            gAuto = 2; gAutoFrames = atoi(argv[i + 1]);
            snprintf(gShotFile, sizeof gShotFile, "%s", argv[i + 2]);
            snprintf(gAutoIp, sizeof gAutoIp, "%s", argv[i + 3]);
        }
        if (!strcmp(argv[i], "--browse-test") && i + 2 < argc) {
            gAuto = 3; gAutoFrames = atoi(argv[i + 1]);
            snprintf(gShotFile, sizeof gShotFile, "%s", argv[i + 2]);
        }
        if (!strcmp(argv[i], "--server")) gServerMode = 1;
    }
#ifdef SERVER_MODE
    gServerMode = 1;
#endif
    if (gServerMode) setvbuf(stdout, NULL, _IONBF, 0);
    gAutoConnect = !gServerMode && !gAuto && !gShotMode;
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) {
        fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
        return 1;
    }
    int hidden = gShotMode || gAuto || gServerMode;
    gWin = SDL_CreateWindow("Zombies Ate My Neighbors - Native Edition",
                            SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                            VIEW_W * WIN_SCALE, VIEW_H * WIN_SCALE,
                            SDL_WINDOW_RESIZABLE | (hidden ? SDL_WINDOW_HIDDEN : 0));
    gRen = SDL_CreateRenderer(gWin, -1, SDL_RENDERER_ACCELERATED | (hidden ? 0 : SDL_RENDERER_PRESENTVSYNC));
    if (!gRen) gRen = SDL_CreateRenderer(gWin, -1, 0);
    SDL_RenderSetLogicalSize(gRen, VIEW_W, VIEW_H);
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "nearest");

    for (int i = 0; i < SDL_NumJoysticks(); i++)
        if (SDL_IsGameController(i)) { gPad = SDL_GameControllerOpen(i); if (gPad) break; }

    texZeke = load_sheet(emb_zeke_png, emb_zeke_png_len, 1);
    texJulie = load_sheet(emb_julie_png, emb_julie_png_len, 1);
    texZombie = load_sheet(emb_zombie_png, emb_zombie_png_len, 2);
    texVict = load_sheet(emb_victims_png, emb_victims_png_len, 1);
    texItems = load_sheet(emb_items_png, emb_items_png_len, 1);
    texDoor = load_sheet(emb_exitdoor_png, emb_exitdoor_png_len, 0);
    texLevel = load_sheet(emb_level_big_png, emb_level_big_png_len, 0);
    memcpy(gWalk, emb_walk_big_bin, sizeof gWalk < emb_walk_big_bin_len ? sizeof gWalk : emb_walk_big_bin_len);
    init_world();
    if (!gAuto && !gServerMode) {
        SDL_AudioSpec want = {0}, have;
        want.freq = 48000; want.format = AUDIO_F32SYS; want.channels = 1; want.samples = 512; want.callback = audio_cb;
        gAudio = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
        if (gAudio) SDL_PauseAudioDevice(gAudio, 0);
    }

    /* legacy --shot for static screens + SP sim */
    if (gShotMode) {
        if (!strcmp(shotState, "options")) gSt = ST_OPTIONS;
        else if (!strcmp(shotState, "lobby")) { gSt = ST_LOBBY; gLobStage = 0; }
        else if (!strcmp(shotState, "charsel")) gSt = ST_CHARSEL;
        else if (!strcmp(shotState, "play")) { gSt = ST_PLAY; gLocalSlot = 0; game_reset(MODE_SP, 0); }
        else if (!strcmp(shotState, "playteams")) { gSt = ST_PLAY; gTeamCount = 4; memset(gKinds, 0, sizeof gKinds); gKinds[0] = 1; gMySlot = 0; gLocalSlot = 0; game_reset(MODE_TEAMS, 0); }
        gMenuT = 1.2f;
        for (int i = 0; i < shotFrames; i++) {
            if (gSt == ST_PLAY) update_game(1.f / 60.f);
            gMenuT += 1.f / 60.f; gZomWalkT += 1.f / 60.f;
        }
        save_frame_png(gShotFile);
        return 0;
    }

    Uint64 pf = SDL_GetPerformanceFrequency(), last = SDL_GetPerformanceCounter();
    int running = 1;
    int pauseIdx = 0;
    long frameNo = 0;
    float snapT = 0;
    unsigned char inputSeq = 0;

    /* dedicated server: boot straight into a hosted lobby, auto-start matches */
    if (gServerMode) {
        gTeamCount = 4;
        if (net_host_open()) {
            gMySlot = -1; gLocalSlot = -1;
            gSt = ST_LOBBY; gLobStage = 1;
            gServerStartT = 8.f;
            printf("SERVER: listening on UDP port %d (%s) - first match in 8s\n", NET_PORT, DEFAULT_SERVER);
        } else {
            printf("SERVER: FAILED to bind port %d\n", NET_PORT);
            return 1;
        }
    } else if (gAutoConnect) {
        /* auto-connect to the public server on launch */
        gAutoConnect = 0;
        if (net_client_open(gLobIp)) {
            gSt = ST_LOBBY; gLobStage = 2;
            gLobbyGot = 0; gJoinReqT = 0; gJoinStartT = gNetTime;
            gMySlot = -1;
        } else {
            gSt = ST_MENU;
        }
    }

    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;
            if (e.type != SDL_KEYDOWN || gAuto) continue;
            SDL_Keycode kc = e.key.keysym.sym;
            switch (gSt) {
                case ST_MENU:
                    if (kc == SDLK_UP || kc == SDLK_w) { gMenuIdx = (gMenuIdx + 2) % 3; play_snd(SND_MENU); }
                    if (kc == SDLK_DOWN || kc == SDLK_s) { gMenuIdx = (gMenuIdx + 1) % 3; play_snd(SND_MENU); }
                    if (kc == SDLK_RETURN || kc == SDLK_z || kc == SDLK_SPACE) {
                        play_snd(SND_CONFIRM);
                        if (gMenuIdx == 0) gSt = ST_CHARSEL;
                        else if (gMenuIdx == 1) { gSt = ST_LOBBY; gLobStage = 0; gLobRow = 0; }
                        else gSt = ST_OPTIONS;
                    }
                    if (kc == SDLK_ESCAPE) running = 0;
                    break;
                case ST_LOBBY:
                    if (gLobStage == 0) {
                        if (kc == SDLK_UP || kc == SDLK_w) { gLobRow = (gLobRow + 3) % 4; play_snd(SND_MENU); }
                        if (kc == SDLK_DOWN || kc == SDLK_s) { gLobRow = (gLobRow + 1) % 4; play_snd(SND_MENU); }
                        if (gLobRow == 0 && (kc == SDLK_LEFT || kc == SDLK_RIGHT || kc == SDLK_a || kc == SDLK_d)) {
                            gTeamCount = gTeamCount == 4 ? 2 : 4; play_snd(SND_MENU);
                        }
                        if (gLobRow == 2) {
                            size_t L = strlen(gLobIp);
                            if (L < 42) {
                                char ch = 0;
                                if (kc >= SDLK_0 && kc <= SDLK_9) ch = (char)('0' + (kc - SDLK_0));
                                else if (kc >= SDLK_KP_1 && kc <= SDLK_KP_9) ch = (char)('1' + (kc - SDLK_KP_1));
                                else if (kc == SDLK_KP_0) ch = '0';
                                else if (kc == SDLK_PERIOD || kc == SDLK_KP_PERIOD) ch = '.';
                                else if (kc >= SDLK_a && kc <= SDLK_z) {
                                    ch = (char)('a' + (kc - SDLK_a));
                                    if (SDL_GetModState() & KMOD_SHIFT) ch = (char)('A' + (kc - SDLK_a));
                                }
                                else if (kc == SDLK_MINUS) ch = '-';
                                if (ch) { gLobIp[L] = ch; gLobIp[L+1] = 0; }
                            }
                            if (kc == SDLK_BACKSPACE && L > 0) gLobIp[L-1] = 0;
                        }
                        if (kc == SDLK_RETURN) {
                            if (gLobRow == 1) {
                                if (net_host_open()) { gLobStage = 1; gLobSelRow = 0; play_snd(SND_CONFIRM); }
                                else msg("PORT 6969 BUSY");
                            } else if (gLobRow == 2) {
                                if (net_client_open(gLobIp)) { gLobStage = 2; gLobSelRow = 0; gLobbyGot = 0; gJoinReqT = 0; gJoinStartT = gNetTime; play_snd(SND_CONFIRM); }
                                else msg("CAN'T REACH HOST");
                            } else if (gLobRow == 3) {
                                if (net_browse_open()) { gLobCount = 0; gLobSel = 0; gLobStage = 3; play_snd(SND_CONFIRM); }
                                else msg("PORT 6969 BUSY");
                            }
                        }
                        if (kc == SDLK_ESCAPE) { net_close(); gSt = ST_MENU; }
                    } else if (gLobStage == 1 || gLobStage == 2) {
                        int n = gTeamCount * 2;
                        if (kc == SDLK_UP || kc == SDLK_w) { gLobSelRow = (gLobSelRow + n - 1) % n; play_snd(SND_MENU); }
                        if (kc == SDLK_DOWN || kc == SDLK_s) { gLobSelRow = (gLobSelRow + 1) % n; play_snd(SND_MENU); }
                        if (gLobSelRow >= n) gLobSelRow = 0;
                        int canEdit = (gLobStage == 1 && gKinds[gLobSelRow] == 0) || gLobSelRow == gMySlot;
                        if (canEdit && (kc == SDLK_LEFT || kc == SDLK_a || kc == SDLK_RIGHT || kc == SDLK_d)) {
                            int dirn = (kc == SDLK_LEFT || kc == SDLK_a) ? -1 : 1;
                            gLobTeam[gLobSelRow] = (unsigned char)((gLobTeam[gLobSelRow] + gTeamCount + dirn) % gTeamCount);
                            play_snd(SND_MENU);
                            if (gLobStage == 2 && gSock != INVALID_SOCKET) {
                                PkEdit e = {6, (unsigned char)gLobSelRow, gLobTeam[gLobSelRow], gLobChar[gLobSelRow]};
                                sendto(gSock, (char *)&e, sizeof e, 0, (struct sockaddr *)&gHostAddr, sizeof gHostAddr);
                            }
                        }
                        if (canEdit && (kc == SDLK_c || kc == SDLK_x)) {
                            gLobChar[gLobSelRow] ^= 1;
                            play_snd(SND_MENU);
                            if (gLobStage == 2 && gSock != INVALID_SOCKET) {
                                PkEdit e = {6, (unsigned char)gLobSelRow, gLobTeam[gLobSelRow], gLobChar[gLobSelRow]};
                                sendto(gSock, (char *)&e, sizeof e, 0, (struct sockaddr *)&gHostAddr, sizeof gHostAddr);
                            }
                        }
                        if (gLobStage == 1 && kc == SDLK_RETURN) {
                            play_snd(SND_CONFIRM);
                            gNetStarted = 1;
                            host_broadcast_lobby();
                            gMySlot = 0; gLocalSlot = 0;
                            game_reset(MODE_TEAMS, 0);
                            gSt = ST_PLAY;
                        }
                        if (kc == SDLK_ESCAPE) { net_close(); gLobStage = 0; }
                    } else if (gLobStage == 3) {
                        if (gLobCount > 0 && (kc == SDLK_UP || kc == SDLK_w)) { gLobSel = (gLobSel + gLobCount - 1) % gLobCount; play_snd(SND_MENU); }
                        if (gLobCount > 0 && (kc == SDLK_DOWN || kc == SDLK_s)) { gLobSel = (gLobSel + 1) % gLobCount; play_snd(SND_MENU); }
                        if (kc == SDLK_RETURN || kc == SDLK_z) {
                            if (gLobCount > 0) {
                                LobbyEntry *e = &gLobList[gLobSel];
                                if (e->started) play_snd(SND_MENU);
                                else {
                                    char ip[16];
                                    snprintf(ip, sizeof ip, "%s", inet_ntoa(*(struct in_addr *)&e->addr));
                                    if (net_client_open(ip)) { gLobStage = 2; gLobSelRow = 0; gLobbyGot = 0; gJoinReqT = 0; gJoinStartT = gNetTime; play_snd(SND_CONFIRM); }
                                    else msg("CONNECT FAILED");
                                }
                            }
                        }
                        if (kc == SDLK_ESCAPE) { net_close(); gLobStage = 0; }
                    }
                    break;
                case ST_OPTIONS:
                    if (kc == SDLK_UP || kc == SDLK_w) { gOptIdx = (gOptIdx + 3) % 4; play_snd(SND_MENU); }
                    if (kc == SDLK_DOWN || kc == SDLK_s) { gOptIdx = (gOptIdx + 1) % 4; play_snd(SND_MENU); }
                    if (kc == SDLK_LEFT || kc == SDLK_RIGHT || kc == SDLK_a || kc == SDLK_d || kc == SDLK_RETURN) {
                        int dirn = (kc == SDLK_LEFT || kc == SDLK_a) ? -1 : 1;
                        play_snd(SND_MENU);
                        if (gOptIdx == 0) {
                            gFullscreen = !gFullscreen;
                            SDL_SetWindowFullscreen(gWin, gFullscreen ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
                        } else if (gOptIdx == 1) { gSmooth = !gSmooth; apply_filter(); }
                        else if (gOptIdx == 2) { gVolume += dirn; if (gVolume < 0) gVolume = 0; if (gVolume > 10) gVolume = 10; play_snd(SND_CONFIRM); }
                        else if (gOptIdx == 3 && kc == SDLK_RETURN) gSt = ST_MENU;
                    }
                    if (kc == SDLK_ESCAPE) gSt = ST_MENU;
                    break;
                case ST_CHARSEL:
                    if (kc == SDLK_LEFT || kc == SDLK_RIGHT || kc == SDLK_a || kc == SDLK_d) { gSelIdx ^= 1; play_snd(SND_MENU); }
                    if (kc == SDLK_RETURN || kc == SDLK_z || kc == SDLK_SPACE) {
                        play_snd(SND_CONFIRM);
                        gLocalSlot = 0;
                        game_reset(MODE_SP, gSelIdx);
                        gSt = ST_PLAY;
                    }
                    if (kc == SDLK_ESCAPE) gSt = ST_MENU;
                    break;
                case ST_PLAY:
                    if (kc == SDLK_ESCAPE || kc == SDLK_p) {
                        if (gSock == INVALID_SOCKET) { gSt = ST_PAUSE; pauseIdx = 0; play_snd(SND_MENU); }
                        else { /* net game: esc leaves */ net_close(); gSt = ST_MENU; }
                    }
                    break;
                case ST_PAUSE:
                    if (kc == SDLK_UP || kc == SDLK_DOWN || kc == SDLK_w || kc == SDLK_s) { pauseIdx ^= 1; play_snd(SND_MENU); }
                    if (kc == SDLK_RETURN || kc == SDLK_z) {
                        play_snd(SND_CONFIRM);
                        if (pauseIdx == 0) gSt = ST_PLAY;
                        else gSt = ST_MENU;
                    }
                    if (kc == SDLK_ESCAPE) gSt = ST_PLAY;
                    break;
                case ST_WIN:
                case ST_GAMEOVER:
                    if (kc == SDLK_RETURN || kc == SDLK_ESCAPE || kc == SDLK_z) { net_close(); gSt = ST_MENU; play_snd(SND_CONFIRM); }
                    break;
            }
        }

        Uint64 now = SDL_GetPerformanceCounter();
        float dt = (float)(now - last) / pf;
        last = now;
        if (dt > 1.f / 30.f) dt = 1.f / 30.f;
        if (gAuto) { dt = 1.f / 60.f; SDL_Delay(6); }
        gMenuT += dt; gZomWalkT += dt; gNetTime += dt;
        frameNo++;

        /* autopilot for net tests */
        if (gAuto == 1) {
            if (frameNo == 30) { gTeamCount = gAutoTeams; net_host_open(); gSt = ST_LOBBY; gLobStage = 1; }
            int joined = 0;
            for (int i = 0; i < MAX_PLAYERS; i++) joined += gClientKnown[i];
            if (gSt == ST_LOBBY && gLobStage == 1 && frameNo > 120 && (joined || frameNo > 1500)) {
                gNetStarted = 1; host_broadcast_lobby();
                gMySlot = 0; gLocalSlot = 0;
                game_reset(MODE_TEAMS, 0);
                gSt = ST_PLAY;
            }
            if (frameNo >= gAutoFrames) { save_frame_png(gShotFile); net_close(); return 0; }
        } else if (gAuto == 2) {
            if (frameNo == 30) { net_client_open(gAutoIp); gSt = ST_LOBBY; gLobStage = 2; gLobbyGot = 0; }
            if (frameNo >= gAutoFrames) { save_frame_png(gShotFile); net_close(); return 0; }
        } else if (gAuto == 3) {
            if (frameNo == 30) { net_browse_open(); gSt = ST_LOBBY; gLobStage = 3; gLobCount = 0; gLobSel = 0; }
            if (frameNo >= gAutoFrames) {
                printf("lobbies %d\n", gLobCount);
                for (int i = 0; i < gLobCount; i++)
                    printf("  %s %d/%d %s\n", gLobList[i].name, gLobList[i].filled, gLobList[i].slots,
                           gLobList[i].started ? "IN GAME" : "WAITING");
                save_frame_png(gShotFile); net_close(); return 0;
            }
        }

        /* network pumps */
        if (gSock != INVALID_SOCKET) {
            if (gHosting) {
                host_poll();
                if (gSt == ST_LOBBY && gLobStage == 1) {
                    gLobbyBcastT -= dt;
                    if (gLobbyBcastT <= 0) { gLobbyBcastT = 0.2f; host_broadcast_lobby(); }
                    if (gServerMode) {
                        gServerStartT -= dt;
                        if (gServerStartT <= 0) {
                            gNetStarted = 1; host_broadcast_lobby();
                            gMySlot = -1; gLocalSlot = -1;
                            game_reset(MODE_TEAMS, 0);
                            gSt = ST_PLAY;
                            printf("SERVER: match started\n");
                        }
                    }
                }
            } else {
                client_poll();
                if (gSt == ST_LOBBY && gLobStage == 2) {
                    gJoinReqT -= dt;
                    if (gJoinReqT <= 0) {
                        gJoinReqT = 0.5f;
                        PkJoin j = {1};
                        sendto(gSock, (char *)&j, sizeof j, 0, (struct sockaddr *)&gHostAddr, sizeof gHostAddr);
                    }
                    if (gNetStarted) { client_setup(); gSt = ST_PLAY; }
                    if (gLobbyGot && gNetTime - gNetLastRx > 6.f) { net_close(); gLobStage = 0; msg("LOST HOST"); }
                    if (!gLobbyGot && gNetTime - gJoinStartT > 6.f) { net_close(); gLobStage = 0; }
                }
                if (gSt == ST_LOBBY && gLobStage == 3) lobby_prune();
                if (gSt == ST_WIN && gNetPhase == 1) { client_setup(); gSt = ST_PLAY; }
            }
            if (gHosting) {
                gBeaconT -= dt;
                if (gBeaconT <= 0) { gBeaconT = 0.5f; host_send_beacon(); }
            }
        }

        if (gSt == ST_PLAY) {
            if (gSock != INVALID_SOCKET && !gHosting) {
                /* net client: send input, render snapshots */
                float ix, iy; int fire;
                read_local_input(&ix, &iy, &fire);
                PkInput pi = {3, (unsigned char)gMySlot, pack_buttons(ix, iy, fire), ++inputSeq};
                sendto(gSock, (char *)&pi, sizeof pi, 0, (struct sockaddr *)&gHostAddr, sizeof gHostAddr);
                if (gNetTime - gNetLastRx > 5.f) { net_close(); gSt = ST_MENU; }
                if (gNetPhase == 2) gSt = ST_WIN;
                /* advance fx/victim anim timers locally for smoothness */
                for (int i = 0; i < MAX_FX; i++) if (gFx[i].used) gFx[i].t += dt * 0.5f;
            } else {
                update_game(dt);
                if (gHosting) {
                    snapT -= dt;
                    if (snapT <= 0) { snapT = 1.f / 30.f; host_send_snapshot(); }
                }
                if (gMode == MODE_TEAMS) {
                    if (gRescued + gEaten == gNumVictims) {
                        gNetPhase = 2;
                        if (gHosting) host_send_snapshot();
                        gSt = ST_WIN;
                        if (gServerMode) { gServerRestartT = 8.f; printf("SERVER: match over - next in 8s\n"); }
                    }
                } else {
                    int anyAlive = gP[0].alive, anyLives = gP[0].lives > 0;
                    if (!anyLives && !anyAlive) gSt = ST_GAMEOVER;
                    if (gRescued + gEaten == gNumVictims && gRescued == 0) gSt = ST_GAMEOVER;
                    if (gDoorOpen) {
                        float dx = gP[0].x - gDoorX, dy = gP[0].y - (gDoorY + 30);
                        if (gP[0].alive && dx * dx + dy * dy < 18 * 18) { gSt = ST_WIN; play_snd(SND_RESCUE); }
                    }
                }
            }
        } else if (gSt == ST_WIN && gHosting) {
            /* keep clients informed the game ended */
            snapT -= dt;
            if (snapT <= 0) { snapT = 0.2f; gNetPhase = 2; host_send_snapshot(); }
            if (gServerMode) {
                gServerRestartT -= dt;
                if (gServerRestartT <= 0) {
                    game_reset(MODE_TEAMS, 0);
                    gNetPhase = 1;
                    gSt = ST_PLAY;
                    host_broadcast_lobby();
                    printf("SERVER: next match\n");
                }
            }
        }

        rerender_current();
        if (gSt == ST_PAUSE) {
            SDL_SetRenderDrawBlendMode(gRen, SDL_BLENDMODE_BLEND);
            SDL_SetRenderDrawColor(gRen, 0, 0, 0, 170);
            SDL_Rect full = { 0, 0, VIEW_W, VIEW_H };
            SDL_RenderFillRect(gRen, &full);
            draw_text_c(VIEW_W / 2, 80, 3, (SDL_Color){110, 235, 70, 255}, "PAUSED");
            draw_text_c(VIEW_W / 2, 130, 2, pauseIdx == 0 ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255}, "RESUME");
            draw_text_c(VIEW_W / 2, 154, 2, pauseIdx == 1 ? (SDL_Color){255, 255, 120, 255} : (SDL_Color){200, 190, 210, 255}, "QUIT TO MENU");
        }
        SDL_RenderPresent(gRen);
    }
    net_close();
    WSACleanup();
    SDL_Quit();
    return 0;
}
