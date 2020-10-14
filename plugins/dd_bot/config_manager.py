from collections import Counter
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters.cqhttp import Bot, Event
from nonebot.permission import GROUP_ADMIN, PRIVATE_FRIEND, SUPERUSER, GROUP_OWNER
from .utils import read_config, Dydb, User, update_config


async def permission_check(bot: Bot, event: Event, state: dict):
    config = await read_config()
    if event.detail_type == 'group':
        group_id = str(event.group_id)
        if True if group_id not in config['groups'] else config['groups'][group_id]['admin']:
            is_admin = await GROUP_ADMIN(bot, event) or await GROUP_OWNER(bot, event) or await PRIVATE_FRIEND(bot, event) or await SUPERUSER(bot, event)
            if is_admin:
                return True
            else:
                # await bot.send(event, '权限不足，无法使用')
                return False
        else:
            return True
    else:
        return True # 私聊默认返回 True


add_uid = on_command('添加主播', rule=to_me() & permission_check, priority=5)

@add_uid.handle()
async def get_args(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@add_uid.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    uid = state['uid']
    config = await read_config()

    dydb = Dydb()
    if uid not in config["status"]: # uid不在配置文件就创建一个
        user = User(uid)
        name = ''
        try: # 应该改uid有效检测逻辑
            user_info = await user.get_info()
            name = user_info["name"]
        except:
            await add_uid.finish("请输入有效的uid")
        config['status'][uid] = 0
        config['uid'][uid] = {'groups': {}, 'users': {}, 'dynamic': 0, 'live': 0, 'name': name}
        config['dynamic']['uid_list'].append(uid) # 主播uid添加至动态列表，在DD机中应删除
        config['live']['uid_list'].append(uid) # 主播uid添加至直播列表
    else:
        name = config['uid'][uid]['name']

    tables = dydb.get_table_list()
    if 'uid' + uid not in tables:
        dydb.create_table('uid'+uid, '(time int primary key, url varchar(50), is_recall boolean)') # 创建uid表

    if event.detail_type == "group": # 检测是否群消息
        group_id = str(event.group_id)
        if 'qq' + group_id not in tables:
            dydb.create_table('qq'+group_id, '(url varchar(50) primary key, message_id int, bot_id int)')
        if group_id not in config["uid"][uid]["groups"]:
            config["uid"][uid]["groups"][group_id] = event.self_id
        else:
            await add_uid.finish(f"您已将{name}（{uid}）添加至该群，请勿重复添加")
        if group_id in config["groups"]:
            config["groups"][group_id]["uid"][uid] = {"live_reminder": True, "dynamic": True, 'at': False}
        else:
            config["groups"][group_id] = {"uid": {uid: {"live_reminder": True, "dynamic": True, 'at': False}}, 'admin': True}
        config['uid'][uid]['dynamic'] += 1
        config['uid'][uid]['live'] += 1
        await update_config(config)
        await add_uid.finish(f"已将{name}（{uid}）添加至该群")

    elif event.detail_type == "private": # 检测是否私聊消息
        user_id = str(event.user_id)
        if user_id not in config["uid"][uid]["users"]:
            config["uid"][uid]["users"][user_id] = event.self_id
        else:
            await add_uid.finish(f"您已添加{name}（{uid}），请勿重复添加")
        if user_id in config["users"]:
            config["users"][user_id]["uid"][uid] = {"live_reminder": True, "dynamic": True} # DD机中应改为 False
        else:
            config["users"][user_id] = {"uid": {uid: {"live_reminder": True, "dynamic": True}}} # DD机中应改为 False
        config['uid'][uid]['dynamic'] += 1 # 动态推送数加一DD机中应注释
        config['uid'][uid]['live'] += 1
        await update_config(config)
        await add_uid.finish(f"已添加{name}（{uid}）")


delete_uid = on_command('删除主播', rule=to_me() & permission_check, priority=5)

@delete_uid.handle()
async def get_args(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@delete_uid.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    uid = state['uid']
    config = await read_config()

    try:
        name = config['uid'][uid]['name']
    except KeyError:
        delete_uid.finish("删除失败，uid不存在")
    if event.detail_type == 'group':
        group_id = str(event.group_id)
        try:
            if config['groups'][group_id]['uid'][uid]['dynamic']:
                config['uid'][uid]['dynamic'] -= 1
            if config['groups'][group_id]['uid'][uid]['live_reminder']:
                config['uid'][uid]['live'] -= 1
            del config['groups'][group_id]['uid'][uid]
            del config['uid'][uid]['groups'][group_id]
            # 如果用户没有关注则删除用户
            if config['groups'][group_id]['uid'] == {} and config['groups'][group_id]['admin']:
                del config['groups'][group_id]
        except KeyError:
            delete_uid.finish("删除失败，uid不存在")
    elif event.detail_type == 'private':
        user_id = str(event.user_id)
        try:
            if config['users'][user_id]['uid'][uid]['dynamic']:
                config['uid'][uid]['dynamic'] -= 1
            if config['users'][user_id]['uid'][uid]['live_reminder']:
                config['uid'][uid]['live'] -= 1
            del config['users'][user_id]['uid'][uid]
            del config['uid'][uid]['users'][user_id]
            # 如果用户没有关注则删除用户
            if config['users'][user_id]['uid'] == {}:
                del config['users'][user_id]
        except KeyError:
            delete_uid.finish("删除失败，uid不存在")
    # 如果无人再订阅动态，就从动态列表中移除
    if config['uid'][uid]['dynamic'] == 0 and uid in config['dynamic']['uid_list']:
        config['dynamic']['uid_list'].remove(uid)
    # 如果无人再订阅直播，就从直播列表中移除
    if config['uid'][uid]['live'] == 0 and uid in config['live']['uid_list']:
        config['live']['uid_list'].remove(uid)
    # 如果没人订阅该主播，则将该主播彻底删除
    if config['uid'][uid]['groups'] == {} and config['uid'][uid]['users'] == {}:
        del config['uid'][uid]
        del config['status'][uid]
    
    # user = User(uid)
    # name = (await user.get_info())['name']
    await update_config(config)
    await delete_uid.finish(f"已删除 {name}（{uid}）")


list_uid = on_command('主播列表', rule=to_me() & permission_check, priority=5)

@list_uid.handle()
async def _(bot: Bot, event: Event, state: dict):
    config = await read_config()
    if event.detail_type == 'group':
        group_id = str(event.group_id)
        try:
            uid_list = config['groups'][group_id]['uid']
        except KeyError:
            uid_list = {}
        message = "以下为该群的订阅列表，可发送“删除主播 uid”进行删除\n\n"
    elif event.detail_type == 'private':
        user_id = str(event.user_id)
        try:
            uid_list = config['users'][user_id]['uid']
        except KeyError:
            uid_list = {}
        message = "以下为您的订阅列表，可发送“删除主播 uid”进行删除\n\n"
    for uid, status in uid_list.items():
        name = config['uid'][uid]['name']
        message += f"【{name}】"
        message += f"直播推送：{'开' if status['live_reminder'] else '关'}，"
        message += f"动态推送：{'开' if status['dynamic'] else '关'}"
        message += f"（{uid}）\n"
    await list_uid.send(message=message)


dynamic_on = on_command('开启动态', rule=to_me() & permission_check, priority=5)

@dynamic_on.handle()
async def handle_first_recive(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@dynamic_on.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    uid = state['uid']
    config = await read_config()

    if event.detail_type == 'group':
        group_id = str(event.group_id)
        try:
            if config['groups'][group_id]['uid'][uid]['dynamic'] == True:
                dynamic_on.finish('请勿重复开启动态推送')
            config['groups'][group_id]['uid'][uid]['dynamic'] = True
            config['uid'][uid]['dynamic'] += 1
        except KeyError:
            dynamic_on.finish("开启失败，uid不存在")
    elif event.detail_type == 'private':
        user_id = str(event.user_id)
        try:
            if config['users'][user_id]['uid'][uid]['dynamic'] == True:
                dynamic_on.finish('请勿重复开启动态推送')
            config['users'][user_id]['uid'][uid]['dynamic'] = True
            config['uid'][uid]['dynamic'] += 1
        except KeyError:
            dynamic_on.finish("开启失败，uid不存在")
    # 如果是第一个开启的，就添加至动态推送列表
    if config['uid'][uid]['dynamic'] == 1:
        config['dynamic']['uid_list'].append(uid)
    name = config['uid'][uid]['name']
    # user = User(uid)
    # name = (await user.get_info())['name']
    await update_config(config)
    await dynamic_on.finish(f"已开启 {name}（{uid}）的动态推送")


dynamic_off = on_command('关闭动态', rule=to_me() & permission_check, priority=5)

@dynamic_off.handle()
async def handle_first_recive(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@dynamic_off.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    uid = state['uid']
    config = await read_config()

    if event.detail_type == 'group':
        group_id = str(event.group_id)
        try:
            if config['groups'][group_id]['uid'][uid]['dynamic'] == False:
                dynamic_off.finish('请勿重复关闭动态推送')
            config['groups'][group_id]['uid'][uid]['dynamic'] = False
            config['uid'][uid]['dynamic'] -= 1
        except KeyError:
            dynamic_off.finish("关闭失败，uid不存在")
    elif event.detail_type == 'private':
        user_id = str(event.user_id)
        try:
            if config['users'][user_id]['uid'][uid]['dynamic'] == False:
                dynamic_off.finish('请勿重复关闭动态推送')
            config['users'][user_id]['uid'][uid]['dynamic'] = False
            config['uid'][uid]['dynamic'] -= 1
        except KeyError:
            dynamic_off.finish("关闭失败，uid不存在")
    # 如果无人再订阅动态，就从动态列表中移除
    if config['uid'][uid]['dynamic'] == 0:
        config['dynamic']['uid_list'].remove(uid)
    name = config['uid'][uid]['name']
    # user = User(uid)
    # name = (await user.get_info())['name']
    await update_config(config)
    await dynamic_off.finish(f"已关闭 {name}（{uid}）的动态推送")


live_on = on_command('开启直播', rule=to_me() & permission_check, priority=5)

@live_on.handle()
async def handle_first_recive(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@live_on.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    uid = state['uid']
    config = await read_config()
    
    if event.detail_type == 'group':
        group_id = str(event.group_id)
        try:
            if config['groups'][group_id]['uid'][uid]['live_reminder']:
                live_on.finish('请勿重复开启直播推送')
            config['groups'][group_id]['uid'][uid]['live_reminder'] = True
            config['uid'][uid]['live'] += 1
        except KeyError:
            live_on.finish("开启失败，uid不存在")
    elif event.detail_type == 'private':
        user_id = str(event.user_id)
        try:
            if config['users'][user_id]['uid'][uid]['live_reminder']:
                live_on.finish('请勿重复开启直播推送')
            config['users'][user_id]['uid'][uid]['live_reminder'] = True
            config['uid'][uid]['live'] += 1
        except KeyError:
            live_on.finish("开启失败，uid不存在")
    # 如果是第一个开启的，就添加至直播推送列表
    if config['uid'][uid]['live'] == 1:
        config['live']['uid_list'].append(uid)
    name = config['uid'][uid]['name']
    # user = User(uid)
    # name = (await user.get_info())['name']
    await update_config(config)
    await live_on.finish(f"已开启 {name}（{uid}）的直播推送")
    

live_off = on_command('关闭直播', rule=to_me() & permission_check, priority=5)

@live_off.handle()
async def handle_first_recive(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@live_off.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    uid = state['uid']
    config = await read_config()

    if event.detail_type == 'group':
        group_id = str(event.group_id)
        try:
            if not config['groups'][group_id]['uid'][uid]['live_reminder']:
                live_off.finish('请勿重复关闭直播推送')
            config['groups'][group_id]['uid'][uid]['live_reminder'] = False
            config['uid'][uid]['live'] -= 1
        except KeyError:
            live_off.finish("关闭失败，uid不存在")
    elif event.detail_type == 'private':
        user_id = str(event.user_id)
        try:
            if not config['users'][user_id]['uid'][uid]['live_reminder']:
                live_off.finish('请勿重复关闭直播推送')
            config['users'][user_id]['uid'][uid]['live_reminder'] = False
            config['uid'][uid]['live'] -= 1
        except KeyError:
            live_off.finish("关闭失败，uid不存在")
    # 如果无人再订阅动态，就从直播列表中移除
    if config['uid'][uid]['live'] == 0:
        config['live']['uid_list'].remove(uid)
    name = config['uid'][uid]['name']
    # user = User(uid)
    # name = (await user.get_info())['name']
    await update_config(config)
    await live_off.finish(f"已关闭 {name}（{uid}）的直播推送")


at_on = on_command('开启at', rule=to_me(), 
    permission=GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND | SUPERUSER, 
    priority=5)

@at_on.handle()
async def handle_first_recive(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@at_on.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    if event.detail_type != 'group':
        await at_on.finish("只有群里才能开启@全体")
    uid = state['uid']
    config = await read_config()

    group_id = event.group_id
    if uid not in config['groups'][str(group_id)]['uid']:
        await at_on.finish("开启失败，uid不存在")
    if config['groups'][str(group_id)]['uid'][uid]['at']:
        await at_on.finish("请勿重复开启@全员")
    config['groups'][str(group_id)]['uid'][uid]['at'] = True
    await update_config(config)
    name = config['uid'][uid]['name']
    await at_on.finish(f"已开启 {name}（{uid}）的 @全体成员")


at_off = on_command('关闭at', rule=to_me(), 
    permission=GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND | SUPERUSER, 
    priority=5)

@at_off.handle()
async def handle_first_recive(bot: Bot, event: Event, state: dict):
    args = str(event.message).strip()
    if args:
        state['uid'] = args

@at_off.got('uid', prompt='请输入主播的uid')
async def _(bot: Bot, event: Event, state: dict):
    if event.detail_type != 'group':
        await at_off.finish("只有群里才能关闭@全体")
    uid = state['uid']
    config = await read_config()

    group_id = event.group_id
    if uid not in config['groups'][str(group_id)]['uid']:
        await at_off.finish("关闭失败，uid不存在")
    if not config['groups'][str(group_id)]['uid'][uid]['at']:
        await at_off.finish("请勿重复关闭@全员")
    config['groups'][str(group_id)]['uid'][uid]['at'] = False
    await update_config(config)
    name = config['uid'][uid]['name']
    await at_off.finish(f"已关闭 {name}（{uid}）的 @全体成员")


permission_on = on_command('开启权限', rule=to_me(), 
    permission=GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND | SUPERUSER, 
    priority=5)

@permission_on.handle()
async def _(bot: Bot, event: Event, state: dict):
    if event.detail_type != 'group':
        await permission_on.finish("只有群里才能设置权限")
    config = await read_config()
    group_id = str(event.group_id)

    if group_id not in config['groups'] or config['groups'][group_id]['admin']:
        await permission_on.finish("请勿重复开启权限")
    else:
        config['groups'][group_id]['admin'] = True

    await update_config(config)
    await permission_on.finish(f"已开启权限限制，只有管理员才能触发指令")


permission_off = on_command('关闭权限', rule=to_me(), 
    permission=GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND | SUPERUSER, 
    priority=5)

@permission_off.handle()
async def _(bot: Bot, event: Event, state: dict):
    if event.detail_type != 'group':
        await permission_off.finish("只有群里才能设置权限")
    config = await read_config()
    group_id = str(event.group_id)

    if group_id not in config['groups']:
        config['groups'][group_id] = {'uid': {}, 'admin': False}
    elif not config['groups'][group_id]['admin']:
        await permission_off.finish("请勿重复关闭权限")
    else:
        config['groups'][group_id]['admin'] = False

    await update_config(config)
    await permission_off.finish(f"已关闭权限限制，所有人都能触发指令")


fix_config = on_command('修复配置', rule=to_me(), 
    permission=GROUP_OWNER | GROUP_ADMIN | PRIVATE_FRIEND | SUPERUSER, 
    priority=5)

@fix_config.handle()
async def _(bot: Bot, event: Event, state: dict):
    config = await read_config()
    dy_counter = Counter() # 动态推送开启用户数统计
    live_counter = Counter() # 直播推送开启用户数统计
    
    del_qq = [] # 没有订阅的QQ号
    # 统计用户开启的订阅数量
    for qq, user in config['users'].items():
        try:
            for uid, status in user['uid'].items():
                if status['dynamic']:
                    dy_counter[uid] += 1
                if 'live' in status and status['live'] or status['live_reminder']:
                    live_counter[uid] += 1
        except KeyError:
            del_qq.append(qq)
    # 删除没有订阅的QQ号
    for qq in del_qq:
        del config['users'][qq]

    del_qq = [] # 没有订阅的QQ号
    # 统计群开启的订阅数量
    for qq, group in config['groups'].items():
        try:
            for uid, status in group['uid'].items():
                if status['dynamic']:
                    dy_counter[uid] += 1
                if 'live' in status and status['live'] or status['live_reminder']:
                    live_counter[uid] += 1
        except KeyError:
            del_qq.append(qq)
    # 删除没有订阅的QQ群号
    for qq in del_qq:
        del config['groups'][qq]
    
    # 给每个QQ号下的 uid 添加@全体设置
    for qq_id in config['groups']:
        for uid in config['groups'][qq_id]['uid']:
            if 'at' not in config['groups'][qq_id]['uid'][uid]:
                config['groups'][qq_id]['uid'][uid]['at'] = False

    # 将 uid 列表中的 live_reminder 替换为 live
    for uid in config['uid']:
        if 'live_reminder' in config['uid'][uid]:
            del config['uid'][uid]['live_reminder']

    # 检查是否有权限选项
    for group_id in config['groups']:
        if 'admin' not in config['groups'][group_id]:
            config['groups'][group_id]['admin'] = True

    # 将动态和直播订阅总数填入对应uid
    for uid, sub_num in dy_counter.items():
        config['uid'][uid]['dynamic'] = sub_num
    for uid, sub_num in live_counter.items():
        config['uid'][uid]['live'] = sub_num
    # 重置动态和直播的爬取列表
    config['dynamic'] = {'uid_list': list(dy_counter), 'index': 0}
    config['live'] = {'uid_list': list(config['status']), 'index': 0}
    await update_config(config)
    await fix_config.finish('修复完成')


__plugin_name__ = 'DD机'
__plugin_usage__ = r"""DD机目前支持的功能有：

主播列表
添加主播 uid
删除主播 uid
开启动态 uid
关闭动态 uid
开启直播 uid
关闭直播 uid
开启at uid
关闭at uid
开启权限
关闭权限


开启权限后,当前群只有管理员或者机器人好友才能触发指令，输入命令时不要忘记空格

其中“uid”请替换为UP的uid，注意是uid不是直播间id

添加后默认开启直播和动态推送，在哪里（群聊/私聊）添加就会在哪里推送
"""