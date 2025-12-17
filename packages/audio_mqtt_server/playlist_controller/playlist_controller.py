"""
Object that controls the playlist of songs for the audio server.
"""

import numpy as np
import random

class PlaylistController:
    def __init__(self):
        # Playlist 1: Jazz (P1)
        self.playlist1 = [
            "P1 - Bad Ideas - Silent Film Dark - Kevin MacLeod.wav",
            "P1 - Bad Ideas Distressed - Kevin MacLeod.wav",
            "P1 - Baila Mi Cumbia - Jimmy Fontanez_Media Right Productions.wav",
            "P1 - Ersatz Bossa John Deley and the 41 Players.wav",
            "P1 - Hit the Lights - Twin Musicom.wav",
            "P1 - Minor Mush - John Deley.wav"
        ]
        # Playlist 2: Classical (P2)
        self.playlist2 = [
            "P2 - Busy Strings - Kevin MacLeod.wav",
            "P2 - Cinematic - Twin Musicom.wav",
            "P2 - Hero Theme - Kevin MacLeod.wav",
            "P2 - Serious Piano - Audionautix.wav",
            "P2 - Bugle-Calls-Mess-Call-USAF-Heritage-of-America-Band.wav"
        ]
        # Playlist 3: Countryfolk (P3)
        self.playlist3 = [
            "P3 - All-Good-In-The-Wood-Audionautix.wav",
            "P3 - Country-Cue-1-Audionautix.wav",
            "P3 - Dobro-Mash-Audionautix.wav",
            "P3 - Mariachi-Snooze-Kevin-MacLeod.wav",
            "P3 - On My Way Home - The 126ers.wav"
        ]
        self.playlist4 = []
        self.playlist5 = []

    def get_playlist(self, playlist_number: int):
        """Returns the shuffled playlist by number (1-5)."""
        if playlist_number == 1:
            random.shuffle(self.playlist1)
            return self.playlist1
        elif playlist_number == 2:
            random.shuffle(self.playlist2)
            return self.playlist2
        elif playlist_number == 3:
            random.shuffle(self.playlist3)
            return self.playlist3
        elif playlist_number == 4:
            random.shuffle(self.playlist4)
            return self.playlist4
        elif playlist_number == 5:
            random.shuffle(self.playlist5)
            return self.playlist5
        else:
            # Default to playlist 1 if invalid number
            random.shuffle(self.playlist1)
            return self.playlist1

    def update_queue_with_random_song(self, playlist: list[str]):
        """
        Queues a random song from combination of all playlists
        """
        combined_playlist = self.playlist1 + self.playlist2 + self.playlist3 + self.playlist4 + self.playlist5
        random.shuffle(combined_playlist)
        return combined_playlist