import os
import traceback
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context

# 定义标记，用于定位自动更新的区域，确保不覆盖用户手动添加的词
START_MARKER = "# --- 自动获取的群成员信息 (脚本自动维护，请勿手动编辑此区域) ---"
END_MARKER = "# --- 自动获取结束 ---"

async def update_group_member_stopwords(context: Context, event: AstrMessageEvent, stop_words_file: str):
    """
    获取群成员昵称和ID，更新到 stop_words.txt 中
    """
    # 1. 检查是否为群聊消息
    group_id = event.get_group_id()
    if not group_id:
        return

    # 2. 获取平台实例
    platform_name = event.get_platform_name()
    platform = context.get_platform(platform_name)
    
    if not platform:
        logger.warning(f"无法获取平台实例: {platform_name}")
        return

    new_stopwords = set()

    # 3. 获取群成员列表 (尝试适配不同平台接口)
    try:
        member_list = []
        
        # 尝试 OneBot V11 / aiocqhttp 标准接口
        if hasattr(platform, "get_group_member_list"):
            member_list = await platform.get_group_member_list(group_id=int(group_id))
        
        # 尝试 Adapter 接口 (如 WeChat)
        elif hasattr(platform, "get_chatroom_member_list"):
             member_list = await platform.get_chatroom_member_list(group_id)
        
        # 如果获取到了成员数据
        if member_list:
            for member in member_list:
                # 获取 ID
                user_id = str(member.get('user_id', '')) or str(member.get('wxid', ''))
                if user_id:
                    new_stopwords.add(user_id)
                
                # 获取 群名片(card) 或 昵称(nickname)
                card = member.get('card', '')
                nickname = member.get('nickname', '')
                
                if card:
                    new_stopwords.add(card)
                if nickname:
                    new_stopwords.add(nickname)
                    
            logger.info(f"已获取群 {group_id} 的成员信息，共 {len(new_stopwords)} 个关键词")
        else:
            # 如果没获取到列表，可能是权限不足或平台不支持，跳过更新
            return

    except Exception as e:
        logger.warning(f"获取群成员列表失败，将跳过更新停用词: {e}")
        return

    if not new_stopwords:
        return

    # 4. 读取并更新文件
    if not os.path.exists(stop_words_file):
        logger.error(f"停用词文件不存在: {stop_words_file}")
        return

    try:
        content = ""
        with open(stop_words_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 分割现有内容，保留 START_MARKER 之前的部分
        pre_content = content
        post_content = ""

        if START_MARKER in content:
            parts = content.split(START_MARKER)
            pre_content = parts[0].strip()
            
            # 如果存在结束标记，保留结束标记之后的内容
            if len(parts) > 1 and END_MARKER in parts[1]:
                end_parts = parts[1].split(END_MARKER)
                if len(end_parts) > 1:
                    post_content = end_parts[1].strip()

        # 构建新的内容块
        new_block = [START_MARKER]
        new_block.extend(list(new_stopwords))
        new_block.append(END_MARKER)
        
        # 组合最终内容：原头部 + 新生成的群成员 + 原尾部(如果有)
        final_content = pre_content + "\n\n" + "\n".join(new_block) + "\n\n" + post_content
        
        # 清理多余空行
        final_content = final_content.strip()

        with open(stop_words_file, 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        logger.info("已将群成员信息写入 stop_words.txt")

    except Exception as e:
        logger.error(f"写入停用词文件失败: {e}")
        logger.error(traceback.format_exc())