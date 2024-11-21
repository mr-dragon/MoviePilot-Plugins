import time
from typing import Any, List, Dict, Tuple, Optional

from app.core.event import eventmanager, Event
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import WebhookEventInfo, ServiceInfo
from app.schemas.types import EventType, MediaType, MediaImageType, NotificationType
from app.utils.web import WebUtils


class ForwardMsgToQW(_PluginBase):
    # 插件名称
    plugin_name = "转发通知到企微"
    # 插件描述
    plugin_desc = "转发通知到企微。"
    # 插件图标
    plugin_icon = "mediaplay.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "dragon"
    # 作者主页
    author_url = "https://github.com/mr-dragon"
    # 插件配置项ID前缀
    plugin_config_prefix = "forwardmsgtoqw_"
    # 加载顺序
    plugin_order = 14
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    mediaserver_helper = None
    _enabled = False
    _add_play_link = False
    _mediaservers = None
    _types = []
    _webhook_msg_keys = {}

    # 拼装消息内容
    _webhook_actions = {
        "library.new": "新入库",
        "system.webhooktest": "测试",
        "playback.start": "开始播放",
        "playback.stop": "停止播放",
        "user.authenticated": "登录成功",
        "user.authenticationfailed": "登录失败",
        "media.play": "开始播放",
        "media.stop": "停止播放",
        "PlaybackStart": "开始播放",
        "PlaybackStop": "停止播放",
        "item.rate": "标记了"
    }
    _webhook_images = {
        "emby": "https://emby.media/notificationicon.png",
        "plex": "https://www.plex.tv/wp-content/uploads/2022/04/new-logo-process-lines-gray.png",
        "jellyfin": "https://play-lh.googleusercontent.com/SCsUK3hCCRqkJbmLDctNYCfehLxsS4ggD1ZPHIFrrAN1Tn9yhjmGMPep2D9lMaaa9eQi"
    }

    def init_plugin(self, config: dict = None):
        self.mediaserver_helper = MediaServerHelper()
        if config:
            self._enabled = config.get("enabled")
            self._types = config.get("types") or []
            self._mediaservers = config.get("mediaservers") or []
            self._add_play_link = config.get("add_play_link", False)

    def service_infos(self, type_filter: Optional[str] = None) -> Optional[Dict[str, ServiceInfo]]:
        """
        服务信息
        """
        if not self._mediaservers:
            logger.warning("尚未配置媒体服务器，请检查配置")
            return None

        services = self.mediaserver_helper.get_services(type_filter=type_filter, name_filters=self._mediaservers)
        if not services:
            logger.warning("获取媒体服务器实例失败，请检查配置")
            return None

        active_services = {}
        for service_name, service_info in services.items():
            if service_info.instance.is_inactive():
                logger.warning(f"媒体服务器 {service_name} 未连接，请检查配置")
            else:
                active_services[service_name] = service_info

        if not active_services:
            logger.warning("没有已连接的媒体服务器，请检查配置")
            return None

        return active_services

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        types_options = [
            {"title": "新入库", "value": "library.new"},
            {"title": "开始播放", "value": "playback.start|media.play|PlaybackStart"},
            {"title": "停止播放", "value": "playback.stop|media.stop|PlaybackStop"},
            {"title": "用户标记", "value": "item.rate"},
            {"title": "测试", "value": "system.webhooktest"},
            {"title": "登录成功", "value": "user.authenticated"},
            {"title": "登录失败", "value": "user.authenticationfailed"},
        ]
        return [
            {
                'component': 'VForm',
                'content': [
                    # 原有配置保持不变
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },

                    # 添加企业微信配置分割线
                    {
                        'component': 'VDivider',
                        'props': {
                            'class': 'my-4'
                        }
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSubheader',
                                        'props': {
                                            'class': 'text-h6',
                                        },
                                        'content': '企业微信配置'
                                    }
                                ]
                            }
                        ]
                    },

                    # 企业微信配置项
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'wecom_corpid',
                                            'label': '企业ID(CorpID)',
                                            'placeholder': '请输入企业ID',
                                            'persistent-placeholder': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'wecom_corpsecret',
                                            'label': '应用Secret',
                                            'placeholder': '请输入应用Secret',
                                            'persistent-placeholder': True,
                                            'type': 'password'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'wecom_agentid',
                                            'label': '应用ID(AgentID)',
                                            'placeholder': '请输入应用ID',
                                            'persistent-placeholder': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'wecom_touser',
                                            'label': '接收用户',
                                            'placeholder': '接收消息的用户，默认@all',
                                            'persistent-placeholder': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },

                    # 添加说明信息
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '企业微信配置说明：\n1. 需要在企业微信管理后台创建应用\n2. CorpID在"我的企业"页面查看\n3. Secret在应用的详情页面查看\n4. AgentID在应用的详情页面查看\n5. 接收用户默认为@all，也可以指定具体用户ID'
                                        }
                                    }
                                ]
                            }
                        ]
                    },

                    # ... 其他原有配置 ...
                ]
            }
        ], {
            "enabled": False,
            "types": []
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.WebhookMessage)
    def send(self, event: Event):
        """
        发送通知消息
        """
        if not self._enabled:
            return

        event_info: WebhookEventInfo = event.event_data
        if not event_info:
            return

        # 不在支持范围不处理
        if not self._webhook_actions.get(event_info.event):
            return

        # 不在选中范围不处理
        msgflag = False
        for _type in self._types:
            if event_info.event in _type.split("|"):
                msgflag = True
                break
        if not msgflag:
            logger.info(f"未开启 {event_info.event} 类型的消息通知")
            return

        expiring_key = f"{event_info.item_id}-{event_info.client}-{event_info.user_name}"
        # 过滤停止播放重复消息
        if str(event_info.event) == "playback.stop" and expiring_key in self._webhook_msg_keys.keys():
            # 刷新过期时间
            self.__add_element(expiring_key)
            return

        # 消息标题
        if event_info.item_type in ["TV", "SHOW"]:
            message_title = f"{self._webhook_actions.get(event_info.event)}剧集 {event_info.item_name}"
        elif event_info.item_type == "MOV":
            message_title = f"{self._webhook_actions.get(event_info.event)}电影 {event_info.item_name}"
        elif event_info.item_type == "AUD":
            message_title = f"{self._webhook_actions.get(event_info.event)}有声书 {event_info.item_name}"
        else:
            message_title = f"{self._webhook_actions.get(event_info.event)}"

        # 消息内容
        message_texts = []
        if event_info.user_name:
            message_texts.append(f"用户：{event_info.user_name}")
        if event_info.device_name:
            message_texts.append(f"设备：{event_info.client} {event_info.device_name}")
        if event_info.ip:
            message_texts.append(f"IP地址：{event_info.ip} {WebUtils.get_location(event_info.ip)}")
        if event_info.percentage:
            percentage = round(float(event_info.percentage), 2)
            message_texts.append(f"进度：{percentage}%")
        if event_info.overview:
            message_texts.append(f"剧情：{event_info.overview}")
        message_texts.append(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}")

        # 消息内容
        message_content = "\n".join(message_texts)

        # 消息图片
        image_url = event_info.image_url
        # 查询剧集图片
        if (event_info.tmdb_id
                and event_info.season_id
                and event_info.episode_id):
            specific_image = self.chain.obtain_specific_image(
                mediaid=event_info.tmdb_id,
                mtype=MediaType.TV,
                image_type=MediaImageType.Backdrop,
                season=event_info.season_id,
                episode=event_info.episode_id
            )
            if specific_image:
                image_url = specific_image
        # 使用默认图片
        if not image_url:
            image_url = self._webhook_images.get(event_info.channel)

        play_link = None
        if self._add_play_link:
            if event_info.server_name:
                service = self.service_infos().get(event_info.server_name)
                if service:
                    play_link = service.instance.get_play_url(event_info.item_id)
            elif event_info.channel:
                services = self.mediaserver_helper.get_services(type_filter=event_info.channel)
                for service in services.values():
                    play_link = service.instance.get_play_url(event_info.item_id)
                    if play_link:
                        break

        if str(event_info.event) == "playback.stop":
            # 停止播放消息，添加到过期字典
            self.__add_element(expiring_key)
        if str(event_info.event) == "playback.start":
            # 开始播放消息，删除过期字典
            self.__remove_element(expiring_key)

        # 发送消息
        self.post_message(mtype=NotificationType.MediaServer,
                          title=message_title, text=message_content, image=image_url, link=play_link)

    def __add_element(self, key, duration=600):
        expiration_time = time.time() + duration
        # 如果元素已经存在，更新其过期时间
        self._webhook_msg_keys[key] = expiration_time

    def __remove_element(self, key):
        self._webhook_msg_keys = {k: v for k, v in self._webhook_msg_keys.items() if k != key}

    def __get_elements(self):
        current_time = time.time()
        # 过滤掉过期的元素
        self._webhook_msg_keys = {k: v for k, v in self._webhook_msg_keys.items() if v > current_time}
        return list(self._webhook_msg_keys.keys())

    def stop_service(self):
        """
        退出插件
        """
        pass
