
from datetime import datetime
from plexapi.server import PlexServer
from functools import cache

@cache
def fetch_item(plex, key):
    return plex.library.fetchItem(key)

class WatchStatus:
    def __init__(self, key:str) -> None:
        self.key = key
        self.watched_count = 0
        self._lasted_viewed_at = None
        self._high_rating = 0
    
    def watch(self)->None:
        self.watched_count += 1

    @property
    def lasted_viewed_at(self):
        return self._lasted_viewed_at

    @property
    def high_rating(self):
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
        return f'{self.key} {self.watched_count} {self.lasted_viewed_at} {self.high_rating}'

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
        for video in plex.library.search(libtype=libtype, unwatched=False):
            if not video.isWatched:
                continue
            self.data.setdefault(video.key, WatchStatus(video.key))
            self.data[video.key].watch()
            self.data[video.key].lasted_viewed_at = video.lastViewedAt
            self.data[video.key].high_rating = video.userRating

    def get_item_rating(self, key:str, high_rating: float=0) -> int:
        item = fetch_item(self.plex, key)
        if item.userRating and item.userRating > high_rating:
            high_rating = item.userRating
        if hasattr(item, "parentKey"):
            return max(high_rating, self.get_item_rating(item.parentKey))
        return high_rating

    def need_delete(self, status):
        all_watched = status.watched_count >= self.user_counts
        any_watched = status.watched_count > 0
        days_last_watched = (datetime.now() - status.lasted_viewed_at).days if status.lasted_viewed_at else 0
        rating = self.get_item_rating(status.key, status.high_rating)
        if  rating > 8:
            return False
        elif all_watched and days_last_watched > 7:
            return True
        elif any_watched and days_last_watched > 14:
            return True
        return False

    def do(self):
        for plex in self.plexs:
            for libtype in ['episode', 'movie']:
                self.cal_unwatch(plex, libtype)

        for status in self.data.values():
            item = fetch_item(self.plex, status.key)
            if self.need_delete(status):
                print('delete', item)
                item.delete()
            else:
                print('pass', item)

if __name__ == '__main__':
    PlexCleaner().do()