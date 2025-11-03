# TTS 批处理分句器 - 支持逐句流式执行
# 使用ComfyUI批处理机制，让TTS节点逐句处理但只加载一次模型

import re
from typing import List

TEXT_TYPE = "STRING"


class TTS_BatchTextSplitter:
    """
    批处理文本分句器
    将长文本分句后，以批处理方式逐句输出，让TTS节点逐句处理
    
    核心机制：
    - 设置 OUTPUT_IS_LIST = (True,) 启用批处理
    - 返回字符串列表
    - ComfyUI自动将列表中的每一项逐个传递给下游节点
    - 下游TTS节点会被多次调用（每次处理一句）
    - TTS模型在第一次加载后保留在内存中，后续调用直接使用
    """
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "dynamicPrompts": True
                }),
                "split_mode": (["竖线分割", "标点符号", "固定长度", "自定义正则", "智能分句"], {
                    "default": "竖线分割"
                }),
                "max_segments": ("INT", {
                    "default": 100,
                    "min": 1,
                    "max": 1000,
                    "step": 1
                }),
            },
            "optional": {
                "split_length": ("INT", {
                    "default": 50,
                    "min": 10,
                    "max": 500,
                    "step": 10
                }),
                "regex_pattern": ("STRING", {
                    "default": r"(?<=[。！？.!?])\s*",
                    "multiline": False
                }),
                "keep_delimiter": ("BOOLEAN", {
                    "default": True
                }),
            }
        }
    
    # 关键：返回STRING类型的列表，让下游节点批处理
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text_batch",)
    FUNCTION = "split_to_batch"
    CATEGORY = "WAS Suite/Text/TTS"
    OUTPUT_IS_LIST = (True,)  # 关键：声明输出是列表，触发批处理
    
    def split_to_batch(self, text, split_mode, max_segments, 
                       split_length=50, regex_pattern=r"(?<=[。！？.!?])\s*",
                       keep_delimiter=True):
        """
        将文本分句并以批处理列表形式返回
        ComfyUI会自动将列表中的每一项逐个传递给下游节点
        """
        
        text = text.strip()
        if not text:
            return ([],)
        
        # 根据模式分句
        segments = []
        
        if split_mode == "竖线分割":
            segments = self._split_by_pipe(text)
        elif split_mode == "标点符号":
            segments = self._split_by_punctuation(text, keep_delimiter)
        elif split_mode == "固定长度":
            segments = self._split_by_length(text, split_length)
        elif split_mode == "自定义正则":
            segments = self._split_by_regex(text, regex_pattern, keep_delimiter)
        elif split_mode == "智能分句":
            segments = self._split_intelligent(text)
        
        segments = [s.strip() for s in segments if s.strip()]
        
        if len(segments) > max_segments:
            print(f"⚠️ TTS分句警告：文本被分为{len(segments)}句，已限制为{max_segments}句")
            segments = segments[:max_segments]
        
        total = len(segments)
        
        if total == 0:
            return ([],)
        
        print(f"\n{'='*80}")
        print(f"📝 TTS批处理分句完成：共 {total} 句")
        print(f"{'='*80}")
        for i, seg in enumerate(segments[:5]):
            print(f"  [{i+1:2d}] {seg[:60]}{'...' if len(seg) > 60 else ''}")
        if total > 5:
            print(f"  ... 还有 {total - 5} 句")
        print(f"{'='*80}\n")
        print(f"🔄 ComfyUI将自动逐句传递给下游TTS节点")
        print(f"📌 TTS节点会被调用 {total} 次（但模型只加载一次）\n")
        
        # 返回列表，ComfyUI会自动批处理
        return (segments,)
    
    def _split_by_pipe(self, text: str) -> List[str]:
        """按照竖线符号 | 分句"""
        segments = text.split('|')
        return segments
    
    def _split_by_punctuation(self, text: str, keep_delimiter: bool = True) -> List[str]:
        """按照中英文标点符号分句"""
        if keep_delimiter:
            pattern = r'[^。！？；…!?.;]+[。！？；…!?.;]+'
            segments = re.findall(pattern, text)
            last_match_end = sum(len(s) for s in segments)
            if last_match_end < len(text):
                remaining = text[last_match_end:].strip()
                if remaining:
                    segments.append(remaining)
        else:
            pattern = r'(?<=[。！？；…!?.;])\s*'
            segments = re.split(pattern, text)
        return segments
    
    def _split_by_length(self, text: str, length: int) -> List[str]:
        """按照固定长度分句"""
        segments = []
        for i in range(0, len(text), length):
            segments.append(text[i:i+length])
        return segments
    
    def _split_by_regex(self, text: str, pattern: str, keep_delimiter: bool = True) -> List[str]:
        """按照自定义正则表达式分句"""
        try:
            segments = re.split(pattern, text)
            return segments
        except re.error as e:
            print(f"❌ 正则表达式错误: {e}")
            return self._split_by_punctuation(text, keep_delimiter)
    
    def _split_intelligent(self, text: str) -> List[str]:
        """智能分句：综合考虑标点、长度和语义"""
        primary_pattern = r'([^。！？!?]+[。！？!?]+)'
        segments = re.findall(primary_pattern, text)
        
        last_match_end = sum(len(s) for s in segments)
        if last_match_end < len(text):
            remaining = text[last_match_end:].strip()
            if remaining:
                segments.append(remaining)
        
        refined_segments = []
        for seg in segments:
            if len(seg) > 100:
                sub_segs = re.split(r'([^，；,;]+[，；,;]+)', seg)
                sub_segs = [s for s in sub_segs if s.strip()]
                refined_segments.extend(sub_segs)
            else:
                refined_segments.append(seg)
        
        final_segments = []
        temp = ""
        for seg in refined_segments:
            seg = seg.strip()
            if len(temp) + len(seg) < 10 and final_segments:
                temp = temp + seg
            else:
                if temp:
                    final_segments.append(temp)
                temp = seg
        if temp:
            final_segments.append(temp)
        
        return final_segments


# 节点注册
NODE_CLASS_MAPPINGS = {
    "TTS_BatchTextSplitter": TTS_BatchTextSplitter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TTS_BatchTextSplitter": "🎙️ TTS 批处理分句器",
}

