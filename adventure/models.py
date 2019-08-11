from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.forms.models import model_to_dict
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
import uuid
from random import choice, randint
from .create_maze import Maze
from django.db.models import Max


class Game(models.Model):
    in_progress = models.BooleanField(default=False)
    # stackoverflow on writing a custom value validator if we want to implement size limiting https://stackoverflow.com/questions/849142/how-to-limit-the-maximum-value-of-a-numeric-field-in-a-django-model
    map_columns = models.PositiveIntegerField(default=5)
    min_room_id = models.IntegerField(default=0)

    def generate_rooms(self):
        room_id = Room.objects.all().aggregate(Max('id'))['id__max']
        if room_id is None:
            self.min_room_id = 0
        else:
            self.min_room_id = room_id + 1
        self.save()
        total_rooms = self.num_rooms()
        
        for id in range(self.min_room_id, total_rooms+self.min_room_id):
            if id == 0:
                new_room = Room(
                    id=id,
                    title=self.generate_title(),
                    description=self.generate_description(),
                    visited=True
                )
                new_room.save()
            else:
                new_room = Room(
                    id=id,
                    title=self.generate_title(),
                    description=self.generate_description()
                )
                new_room.save()

    def generate_maze(self):

        def room_north(loc):
            return loc - self.map_columns
        def room_south(loc):
            return loc + self.map_columns
        def room_east(loc):
            return loc + 1
        def room_west(loc):
            return loc - 1

        maze = Maze(self.map_columns)
        i = 0
        for room in maze.grid:
            db_room = Room.objects.get(id=i+self.min_room_id)
            db_room.n = -1 if room.north else room_north(i+self.min_room_id)
            db_room.s = -1 if room.south else room_south(i+self.min_room_id)
            db_room.e = -1 if room.east else room_east(i+self.min_room_id)
            db_room.w = -1 if room.west else room_west(i+self.min_room_id)
            db_room.save()
            i += 1
    
    def generate_end(self):
        # Get starting room
        first_room = Room.objects.get(id=self.min_room_id)
        # The furthest rooms will be stored in this array
        furthest_rooms = [first_room]
        # All visited rooms will be stored in this array
        visited_rooms = []
        # Each time a further room is found the loop will run again
        further_found = True

        # While further rooms are being found
        while further_found:
            further_found = False
            # For each room
            for room in furthest_rooms:
                n = room.n > -1 and room.n not in visited_rooms
                s = room.s > -1 and room.s not in visited_rooms
                e = room.e > -1 and room.e not in visited_rooms
                w = room.w > -1 and room.w not in visited_rooms

                # If there's a further room that has not been visited
                if n or s or e or w:

                    # Add this room to visited_rooms
                    # Remove it from furthest rooms (because a further room was found)
                    further_found = True
                    visited_rooms.append(room.id)
                    furthest_rooms.remove(room)
                    # Add any further rooms to furthest_rooms
                    if n:
                        applicable_room = Room.objects.get(id=room.n)
                        furthest_rooms.append(applicable_room)
                    if s:
                        applicable_room = Room.objects.get(id=room.s)
                        furthest_rooms.append(applicable_room)
                    if e:
                        applicable_room = Room.objects.get(id=room.e)
                        furthest_rooms.append(applicable_room)
                    if w:
                        applicable_room = Room.objects.get(id=room.w)
                        furthest_rooms.append(applicable_room)
                # If this room has no n, e, s, or w neighbor that has NOT been visited
                # And if there's more than one room in the furthest_rooms list
                elif len(furthest_rooms) > 1:
                    # Then remove it
                    furthest_rooms.remove(room)
        
        # Set the end column to True on the furthest room
        furthest_room = furthest_rooms.pop()
        furthest_room.end = True
        furthest_room.save()

    def all_rooms(self):
        last_room_id = self.min_room_id+self.num_rooms()-1
        room_list = list(Room.objects.filter(
            id__gte=self.min_room_id, id__lte=last_room_id))
        room_list = [model_to_dict(room) for room in room_list]
        return room_list

    def num_rooms(self):
        return self.map_columns * self.map_columns

    def num_players(self):
        return Player.objects.filter(game_id=self.id).count()

    def get_games_UUIDs(self, player_uuid):
        players_list = list(Player.objects.filter(game_id=self.id))
        for i in range(len(players_list)):
            players_list[i] = model_to_dict(players_list[i])['uuid']
        return list(filter(lambda p_uuid: p_uuid !=
                           player_uuid, players_list))

    def reset_players(self):
        Player.objects.filter(game_id=self.id).update(current_room=-1,game_id=-1)

    @staticmethod
    def generate_title():
        adjectives = [
            "dirty", "dusty", "dark", "damp", "cold", "dim", "gloomy", "wet", "empty", "large", "deep", "long", "moist", "volcanic", "spacious", "gigantic",
            "deep", "warm", "dry", "subterranean", "small", "underwater", "unnatural", "circular", "gigantic", "drafty", "rigid", "cramped", "dreary", "smoky",
            "frightful", "vacant", "lifeless", "glacial", "dreadful", "sacred", "rocky", "fragrant", "artificial", "solitary", "oblong", "dank", "moss-covered", "uninhabited", "volcanic",
        ]
        nouns = [
            "abyss", "chasm", "hollow", "crevice", "tunnel", "hole", "grotto", "cavity", "hollow", "den", "burrow", "chamber", "shelter", "expanse", "narrows", "outlook", "overlook", "peak",
            "gully", "ditch", "fissure", "sinkhole", "rift", "channel", "interior", "bunker", "pool", "tomb",
        ]
        adverb = [
            "quietly", "loudly", "secretly", "fast", "well", "quickly", "easily", "slowly", "lowly", "accidentally", "badly", "carefully", "closely", "cheerfully", "beautifully", "worriedly",
            "wishfully", "grimly", "eagerly"
        ]
        where = [
            "towards", "there", "inside", "here", "back", "far", "above", "abroad", "behind", "away", "outside", "nearby", "downstairs", "indoor", "in", "out", "elsewhere", "anywhere"
        ]
        how_much = [
            "fully", "almost", "rather", "extremely", "entirely", "too", "fairly", "very", "just", "barely", "enough", "deeply", "completely", "quite", "a good deal", "a lot", "a few", "much",
            "some", "many", "lots", "little", "nothing"
        ]
        when = [
            "last year", "last month", "today", "tomorrow", "last week", "later", "soon", "now", "yesterday", "tonight", "already", "then"
        ]
        how_often = [
            "never", "sometimes", "often", "usually", "generally", "occasionally", "seldom", "rarely", "normally", "frequently", "hardly ever", "always"
        ]
        action_verb = [
            "run", "dance", "slide", "jump", "think", "do", "go", "stand", "smile", "listen", "walk", "laugh", "cough", "play", "run", "would", "should", "do", "can", "did", "could", "may",
            "must", "eat", "think", "bring", "hold", "buy", "lay", "catch", "redo"
        ]
        title_adlibs = [
            "adjective noun",
            "how_much adjective noun",
            "how_often adjective noun",
            "The where noun",
        ]
        title = choice(title_adlibs)
        title = title.replace("adjective", choice(adjectives))
        title = title.replace("noun", choice(nouns))
        #title = title.replace("adverb", choice(adverb))
        title = title.replace("where", choice(where))
        title = title.replace("how_much", choice(how_much))
        # title = title.replace("when", choice(when))
        title = title.replace("how_often", choice(how_often))
        # title = title.replace("verb", choice(verbs))
        return title

    @staticmethod
    def generate_description():
        adjectives = [
            "dirty", "dusty", "dark", "damp", "cold", "dim", "gloomy", "wet", "empty", "large", "deep", "long", "moist", "volcanic", "spacious", "gigantic",
            "deep", "warm", "dry", "subterranean", "small", "underwater", "unnatural", "circular", "gigantic", "drafty", "rigid", "cramped", "dreary", "smoky",
            "frightful", "vacant", "lifeless", "glacial", "dreadful", "sacred", "rocky", "fragrant", "artificial", "solitary", "oblong", "dank", "moss-covered", "uninhabited", "volcanic",
        ]
        nouns = [
            "abyss", "chasm", "hollow", "crevice", "tunnel", "hole", "grotto", "cavity", "hollow", "den", "burrow", "chamber", "shelter", "expanse", "narrows", "outlook", "overlook", "peak",
            "gully", "ditch", "fissure", "sinkhole", "rift", "channel", "interior", "bunker", "pool", "tomb",
        ]
        adverb = [
            "quietly", "loudly", "secretly", "fast", "well", "quickly", "easily", "slowly", "lowly", "accidentally", "badly", "carefully", "closely", "cheerfully", "beautifully", "worriedly",
            "wishfully", "grimly", "eagerly"
        ]
        where = [
            "towards", "there", "inside", "here", "back", "far", "above", "abroad", "behind", "away", "outside", "nearby", "downstairs", "indoor", "in", "out", "elsewhere", "anywhere"
        ]
        how_much = [
            "fully", "almost", "rather", "extremely", "entirely", "too", "fairly", "very", "just", "barely", "enough", "deeply", "completely", "quite", "a good deal", "a lot", "a few", "much",
            "some", "many", "lots", "little", "nothing"
        ]
        when = [
            "last year", "last month", "today", "tomorrow", "last week", "later", "soon", "now", "yesterday", "tonight", "already", "then"
        ]
        how_often = [
            "never", "sometimes", "often", "usually", "generally", "occasionally", "seldom", "rarely", "normally", "frequently", "hardly ever", "always"
        ]
        action_verb = [
            "run", "dance", "slide", "jump", "think", "do", "go", "stand", "smile", "listen", "walk", "laugh", "cough", "play", "run", "would", "should", "do", "can", "did", "could", "may",
            "must", "eat", "think", "bring", "hold", "buy", "lay", "catch", "redo"
        ]
        description_adlibs = [
            "Its adjective noun awaits!",
            # "I how_often come here",
            #"I usually action_verb here",
            # "how_often I feel lost",
            # "It's how_often adjective here"
        ]
        description = choice(description_adlibs)
        description = description.replace("adjective", choice(adjectives))
        description = description.replace("noun", choice(nouns))
        # description = description.replace("adverb", choice(adverb))
        # description = description.replace("where", choice(where))
        # description = description.replace("how_much", choice(how_much))
        # description = description.replace("when", choice(when))
        # description = description.replace("how_often", choice(how_often))
        # description = description.replace("action_verb", choice(action_verb))
        return description


class Room(models.Model):
    title = models.CharField(max_length=50, default="DEFAULT TITLE")
    description = models.CharField(
        max_length=500, default="DEFAULT DESCRIPTION")
    visited = models.BooleanField(default=False)
    end = models.BooleanField(default=False)
    n = models.IntegerField(default=-1)
    s = models.IntegerField(default=-1)
    e = models.IntegerField(default=-1)
    w = models.IntegerField(default=-1)

    def __str__(self):
        return f'Title: {self.title}, Description: {self.description} \n N: {self.n} S: {self.s} W: {self.w} E: {self.e}'

    # def n_room(self):
    #     try:
    #         return Room.objects.get(id=self.n)
    #     except Room.DoesNotExist:
    #         return None

    # def s_room(self):
    #     try:
    #         return Room.objects.get(id=self.s)
    #     except Room.DoesNotExist:
    #         return None

    # def e_room(self):
    #     try:
    #         return Room.objects.get(id=self.e)
    #     except Room.DoesNotExist:
    #         return None

    # def w_room(self):
    #     try:
    #         return Room.objects.get(id=self.w)
    #     except Room.DoesNotExist:
    #         return None

    def player_usernames(self, currentPlayerID):
        return [p.user.username for p in Player.objects.filter(current_room=self.id) if p.user.id != int(currentPlayerID)]

    def player_UUIDs(self, currentPlayerID):
        return [p.uuid for p in Player.objects.filter(current_room=self.id) if p.user.id != int(currentPlayerID)]


class Player(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True)
    current_room = models.IntegerField(default=-1)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    game_id = models.IntegerField(default=-1)
    moves = models.IntegerField(default=0)

    def initialize(self, game_id, min_room_id):
        self.current_room = min_room_id
        self.game_id = game_id
        self.moves = 0

    def room(self):
        try:
            # print(f"searching for room: {self.current_room}")
            return Room.objects.get(id=self.current_room)
        except Room.DoesNotExist:
            return None

    def game(self):
        try:
            # print(f"searching for game: {self.game_id}")
            return Game.objects.get(id=self.game_id)
        except Game.DoesNotExist:
            return None

# These callbacks run after a row in the User document is saved
@receiver(post_save, sender=User)
def create_user_player(sender, instance, created, **kwargs):
    if created:
        Player.objects.create(user=instance)
        Token.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_player(sender, instance, **kwargs):
    instance.player.save()
