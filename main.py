
from datetime import date, datetime, timedelta
from plexapi.server import PlexServer
from functools import lru_cache

@lru_cache(None)
def fetch_item(plex, key):
    return plex.library.fetchItem(key)

class WatchStatus:
    def __init__(self, key:str) -> None:
        self.key = key
        self.watched_count = 0
        self._lasted_viewed_at = None
        self._high_rating = 0
        self._meida_type = None
    
    def watch(self)->None:
        self.watched_count += 1

    def is_music(self)->bool:
        return self._meida_type == 'music'

    def is_video(self)->bool:
        return self._meida_type == 'video'

    @property
    def media_type(self) -> str:
        return self._meida_type

    @media_type.setter
    def media_type(self, value: str) -> None:
        if value == 'track':
            self._meida_type = 'music'
        else:
            self._meida_type = 'video'

    @property
    def lasted_viewed_at(self) -> datetime:
        return self._lasted_viewed_at

    @property
    def high_rating(self) -> int:
        return self._high_rating
    
    @lasted_viewed_at.setter
    def lasted_viewed_at(self, lasted_viewed_at: datetime) -> None:
        if not self._lasted_viewed_at:
            self._lasted_viewed_at = lasted_viewed_at
        elif lasted_viewed_at > self._lasted_viewed_at:
            self._lasted_viewed_at = lasted_viewed_at
    
    @high_rating.setter
    def high_rating(self, high_rating: int) -> None:
        if high_rating and self._high_rating < high_rating:
            self._high_rating = high_rating

    
    def __str__(self) -> str:
        return f'{self.key} {self.watched_count} {self.lasted_viewed_at} {self.high_rating} {self.media_type}'

    __repr__ = __str__
    


class PlexCleaner:

    def __init__(self) -> None:
        self.plex = PlexServer()

        account = self.plex.myPlexAccount()

        user_plexs = [PlexServer(self.plex._baseurl, user.get_token(self.plex.machineIdentifier)) for user in account.users()]

        self.plexs = user_plexs + [self.plex]
        self.user_counts = len(self.plexs)
        self.data = {}


    def cal_unwatch(self, plex, libtype):
        for media in plex.library.search(libtype=libtype, unwatched=False):
            ws = WatchStatus(media.ratingKey)
            ws.media_type = libtype

            if ws.is_music():
                if media.viewCount == 0: 
                    continue
            elif not media.isWatched:
                continue

            self.data[ws.key] = ws
            if ws.is_video():
                self.data[ws.key].watch()
                self.data[ws.key].lasted_viewed_at = media.lastViewedAt
            self.data[ws.key].high_rating = self.get_item_rating(plex, ws.key)

    def get_item_rating(self, plex:PlexServer ,key:str, high_rating: float=0) -> int:
        item = fetch_item(plex, key)
        if item.userRating and item.userRating > high_rating:
            high_rating = item.userRating
        if hasattr(item, "parentKey"):
            return self.get_item_rating(plex,item.parentKey, high_rating)
        return high_rating

    def delete(self, status: WatchStatus):
        fetch_item(self.plex, status.key).delete()

    def delete_rule(self, ws: WatchStatus):
        all_watched = ws.watched_count >= self.user_counts
        any_watched = ws.watched_count > 0
        days_last_watched = (datetime.now() - ws.lasted_viewed_at).days if ws.lasted_viewed_at else 0
        delete_at = lambda lasted_view_at, keeping_days: (lasted_view_at-timedelta(days=keeping_days)).date().strftime('%Y-%m-%d')
        rating = ws.high_rating
        if ws.is_music():
            if 0 < rating < 3: 
                print('Delete', fetch_item(self.plex, ws.key), 'because rating is', rating)
                self.delete(ws)

        if ws.is_video():
            if rating > 8:
                print('Pass', fetch_item(self.plex, ws.key), 'because rating is', rating)
            elif any_watched:
                if days_last_watched > 15:
                    print('Delete', fetch_item(self.plex, ws.key), 'because any member watched and last watched more than 15 days, at', ws.lasted_viewed_at.date().strftime('%Y-%m-%d'),'.')
                    self.delete(ws)
                else:
                    print('Pass', fetch_item(self.plex, ws.key), 'because any member watched not at delete teime, will delete after', delete_at(ws.lasted_viewed_at ,15),'.')
            elif all_watched: 
                if days_last_watched > 7:
                    print('Delete', fetch_item(self.plex, ws.key), 'because all members watched and last watched more than 7 days, at', ws.lasted_viewed_at.date().strftime('%Y-%m-%d'),'.')
                    self.delete(ws)
                else:
                    print('Pass', fetch_item(self.plex, ws.key), 'because all members watched not at delete teime, will delete after', delete_at(ws.lasted_viewed_at ,7),'.')
            else:
                print('Warning', fetch_item(self.plex, ws.key), 'should not go here')

    def do(self):
        for plex in self.plexs:
            for libtype in ['episode', 'movie', 'track']:
                self.cal_unwatch(plex, libtype)

        for status in self.data.values(): 
            self.delete_rule(status)

if __name__ == '__main__':
    PlexCleaner().do()