import json
import re
from typing import List, Union, Optional, Dict

from app.core.config import settings
from app.log import logger
from app.utils.http import RequestUtils
from app.utils.singleton import Singleton
from app.utils.string import StringUtils


class Jellyfin(metaclass=Singleton):

    def __init__(self):
        self._host = settings.JELLYFIN_HOST
        if self._host:
            if not self._host.endswith("/"):
                self._host += "/"
            if not self._host.startswith("http"):
                self._host = "http://" + self._host
        self._apikey = settings.JELLYFIN_API_KEY
        self._user = self.get_user()
        self._serverid = self.get_server_id()

    def get_jellyfin_librarys(self) -> List[dict]:
        """
        获取Jellyfin媒体库的信息
        """
        if not self._host or not self._apikey:
            return []
        req_url = f"{self._host}Users/{self._user}/Views?api_key={self._apikey}"
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json().get("Items")
            else:
                logger.error(f"Users/Views 未获取到返回数据")
                return []
        except Exception as e:
            logger.error(f"连接Users/Views 出错：" + str(e))
            return []

    def get_user_count(self) -> int:
        """
        获得用户数量
        """
        if not self._host or not self._apikey:
            return 0
        req_url = "%sUsers?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return len(res.json())
            else:
                logger.error(f"Users 未获取到返回数据")
                return 0
        except Exception as e:
            logger.error(f"连接Users出错：" + str(e))
            return 0

    def get_user(self, user_name: str = None) -> Optional[Union[str, int]]:
        """
        获得管理员用户
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sUsers?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                users = res.json()
                # 先查询是否有与当前用户名称匹配的
                if user_name:
                    for user in users:
                        if user.get("Name") == user_name:
                            return user.get("Id")
                # 查询管理员
                for user in users:
                    if user.get("Policy", {}).get("IsAdministrator"):
                        return user.get("Id")
            else:
                logger.error(f"Users 未获取到返回数据")
        except Exception as e:
            logger.error(f"连接Users出错：" + str(e))
        return None

    def authenticate(self, username: str, password: str) -> Optional[bool]:
        """
        用户认证
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sUsers/authenticatebyname" % self._host
        try:
            res = RequestUtils(content_type="application/json").post_res(
                url=req_url,
                data=json.dumps({
                    "Username": username,
                    "Pw": password
                })
            )
            if res:
                auth_token = res.json().get("AccessToken")
                if auth_token:
                    logger.info(f"用户 {username} Jellyfin认证成功")
                    return True
            else:
                logger.error(f"Users/AuthenticateByName 未获取到返回数据")
        except Exception as e:
            logger.error(f"连接Users/AuthenticateByName出错：" + str(e))
        return None

    def get_server_id(self) -> Optional[str]:
        """
        获得服务器信息
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sSystem/Info?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json().get("Id")
            else:
                logger.error(f"System/Info 未获取到返回数据")
        except Exception as e:
            logger.error(f"连接System/Info出错：" + str(e))
        return None

    def get_activity_log(self, num: int = 30) -> List[dict]:
        """
        获取Jellyfin活动记录
        """
        if not self._host or not self._apikey:
            return []
        req_url = "%sSystem/ActivityLog/Entries?api_key=%s&Limit=%s" % (self._host, self._apikey, num)
        ret_array = []
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                ret_json = res.json()
                items = ret_json.get('Items')
                for item in items:
                    if item.get("Type") == "SessionStarted":
                        event_type = "LG"
                        event_date = re.sub(r'\dZ', 'Z', item.get("Date"))
                        event_str = "%s, %s" % (item.get("Name"), item.get("ShortOverview"))
                        activity = {"type": event_type, "event": event_str,
                                    "date": StringUtils.get_time(event_date)}
                        ret_array.append(activity)
                    if item.get("Type") in ["VideoPlayback", "VideoPlaybackStopped"]:
                        event_type = "PL"
                        event_date = re.sub(r'\dZ', 'Z', item.get("Date"))
                        activity = {"type": event_type, "event": item.get("Name"),
                                    "date": StringUtils.get_time(event_date)}
                        ret_array.append(activity)
            else:
                logger.error(f"System/ActivityLog/Entries 未获取到返回数据")
                return []
        except Exception as e:
            logger.error(f"连接System/ActivityLog/Entries出错：" + str(e))
            return []
        return ret_array

    def get_medias_count(self) -> Optional[dict]:
        """
        获得电影、电视剧、动漫媒体数量
        :return: MovieCount SeriesCount SongCount
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sItems/Counts?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                return res.json()
            else:
                logger.error(f"Items/Counts 未获取到返回数据")
                return {}
        except Exception as e:
            logger.error(f"连接Items/Counts出错：" + str(e))
            return {}

    def __get_jellyfin_series_id_by_name(self, name: str, year: str) -> Optional[str]:
        """
        根据名称查询Jellyfin中剧集的SeriesId
        """
        if not self._host or not self._apikey or not self._user:
            return None
        req_url = "%sUsers/%s/Items?api_key=%s&searchTerm=%s&IncludeItemTypes=Series&Limit=10&Recursive=true" % (
            self._host, self._user, self._apikey, name)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                res_items = res.json().get("Items")
                if res_items:
                    for res_item in res_items:
                        if res_item.get('Name') == name and (
                                not year or str(res_item.get('ProductionYear')) == str(year)):
                            return res_item.get('Id')
        except Exception as e:
            logger.error(f"连接Items出错：" + str(e))
            return None
        return ""

    def get_movies(self, title: str, year: str = None) -> Optional[List[dict]]:
        """
        根据标题和年份，检查电影是否在Jellyfin中存在，存在则返回列表
        :param title: 标题
        :param year: 年份，为空则不过滤
        :return: 含title、year属性的字典列表
        """
        if not self._host or not self._apikey or not self._user:
            return None
        req_url = "%sUsers/%s/Items?api_key=%s&searchTerm=%s&IncludeItemTypes=Movie&Limit=10&Recursive=true" % (
            self._host, self._user, self._apikey, title)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                res_items = res.json().get("Items")
                if res_items:
                    ret_movies = []
                    for res_item in res_items:
                        if res_item.get('Name') == title and (
                                not year or str(res_item.get('ProductionYear')) == str(year)):
                            ret_movies.append(
                                {'title': res_item.get('Name'), 'year': str(res_item.get('ProductionYear'))})
                            return ret_movies
        except Exception as e:
            logger.error(f"连接Items出错：" + str(e))
            return None
        return []

    def get_tv_episodes(self,
                        title: str = None,
                        year: str = None,
                        tmdb_id: int = None,
                        season: int = None) -> Optional[Dict[str, list]]:
        """
        根据标题和年份和季，返回Jellyfin中的剧集列表
        :param title: 标题
        :param year: 年份
        :param tmdb_id: TMDBID
        :param season: 季
        :return: 集号的列表
        """
        if not self._host or not self._apikey or not self._user:
            return None
        # 查TVID
        item_id = self.__get_jellyfin_series_id_by_name(title, year)
        if item_id is None:
            return None
        if not item_id:
            return {}
        # 验证tmdbid是否相同
        item_tmdbid = self.get_iteminfo(item_id).get("ProviderIds", {}).get("Tmdb")
        if tmdb_id and item_tmdbid:
            if str(tmdb_id) != str(item_tmdbid):
                return {}
        if not season:
            season = ""
        try:
            req_url = "%sShows/%s/Episodes?season=%s&&userId=%s&isMissing=false&api_key=%s" % (
                self._host, item_id, season, self._user, self._apikey)
            res_json = RequestUtils().get_res(req_url)
            if res_json:
                res_items = res_json.json().get("Items")
                # 返回的季集信息
                season_episodes = {}
                for res_item in res_items:
                    season_index = res_item.get("ParentIndexNumber")
                    if not season_index:
                        continue
                    if season and season != season_index:
                        continue
                    episode_index = res_item.get("IndexNumber")
                    if not episode_index:
                        continue
                    if not season_episodes.get(season_index):
                        season_episodes[season_index] = []
                    season_episodes[season_index].append(episode_index)
                return season_episodes
        except Exception as e:
            logger.error(f"连接Shows/Id/Episodes出错：" + str(e))
            return None
        return {}

    def get_remote_image_by_id(self, item_id: str, image_type: str) -> Optional[str]:
        """
        根据ItemId从Jellyfin查询TMDB图片地址
        :param item_id: 在Emby中的ID
        :param image_type: 图片的类弄地，poster或者backdrop等
        :return: 图片对应在TMDB中的URL
        """
        if not self._host or not self._apikey:
            return None
        req_url = "%sItems/%s/RemoteImages?api_key=%s" % (self._host, item_id, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res:
                images = res.json().get("Images")
                for image in images:
                    if image.get("ProviderName") == "TheMovieDb" and image.get("Type") == image_type:
                        return image.get("Url")
            else:
                logger.error(f"Items/RemoteImages 未获取到返回数据")
                return None
        except Exception as e:
            logger.error(f"连接Items/Id/RemoteImages出错：" + str(e))
            return None
        return None

    def refresh_root_library(self) -> bool:
        """
        通知Jellyfin刷新整个媒体库
        """
        if not self._host or not self._apikey:
            return False
        req_url = "%sLibrary/Refresh?api_key=%s" % (self._host, self._apikey)
        try:
            res = RequestUtils().post_res(req_url)
            if res:
                return True
            else:
                logger.info(f"刷新媒体库失败，无法连接Jellyfin！")
        except Exception as e:
            logger.error(f"连接Library/Refresh出错：" + str(e))
            return False

    def get_iteminfo(self, itemid: str) -> dict:
        """
        获取单个项目详情
        """
        if not itemid:
            return {}
        if not self._host or not self._apikey:
            return {}
        req_url = "%sUsers/%s/Items/%s?api_key=%s" % (
            self._host, self._user, itemid, self._apikey)
        try:
            res = RequestUtils().get_res(req_url)
            if res and res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"连接Users/Items出错：" + str(e))
            return {}

    def get_webhook_message(self, message: dict) -> dict:
        """
        解析Jellyfin报文
        """
        eventItem = {'event': message.get('NotificationType', ''),
                     'item_name': message.get('Name'),
                     'user_name': message.get('NotificationUsername'),
                     "channel": "jellyfin"
                     }

        # 获取消息图片
        if eventItem.get("item_id"):
            # 根据返回的item_id去调用媒体服务器获取
            eventItem['image_url'] = self.get_remote_image_by_id(item_id=eventItem.get('item_id'),
                                                                 image_type="Backdrop")

        return eventItem
