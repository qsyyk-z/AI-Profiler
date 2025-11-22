#!/usr/bin/env python
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
import re
import time
import openai
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SkillValidator:    
    def __init__(self, threshold: float = 0.9, max_retries: int = 2):
        """
        初始化验证器
        
        Args:
            threshold: 覆盖率阈值，默认90%
            max_retries: 最大重试次数，默认2次
        """
        self.threshold = threshold
        self.max_retries = max_retries
        logger.info(f"技能点验证器初始化完成，覆盖率阈值设置为 {threshold * 100}%，最大重试次数: {max_retries}")
    
    def load_structured_content(self, content_path: str) -> str:
        
        try:
            with open(content_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                result = []
                for i in data:
                    result.append(i['content'])
                return result
        except Exception as e:
            logger.error(f"加载结构化内容失败: {str(e)}")
            return ""
    
    def load_skills(self, skills_data: Dict[str, Any]) -> List[str]:
        skills_list = []
        try:
            skills = skills_data.get('skills', [])
            for skill in skills:
                if isinstance(skill, dict):
                    for value in skill.values():
                        skills_list.append(str(value))
                elif isinstance(skill, str):
                    skills_list.append(skill)
            logger.info(f"成功提取 {len(skills_list)} 个技能点")
        except Exception as e:
            logger.error(f"加载技能点数据失败: {str(e)}")
        return skills_list
    
    def calculate_coverage(self, original_content: str, skills: List[str]) -> float:
        """
        计算技能点在原始内容中的覆盖率
        
        Args:
            original_content: 原始PPT内容
            skills: 技能描述列表
            
        Returns:
            覆盖率百分比 (0.0 - 1.0)
        """
        if not original_content or not skills:
            logger.warning("原始内容或技能点列表为空，无法计算覆盖率")
            return 0.0
        
        # 预处理文本
        def preprocess(text: str) -> str:
            # 转小写
            text = text.lower()
            # 移除标点符号和多余空格
            text = re.sub(r'[^\w\s]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        
        # 分词
        def tokenize(text: str) -> List[str]:
            return text.split()
        
        # 预处理原始内容
        processed_content = preprocess(original_content)
        content_tokens = tokenize(processed_content)
        
        # 计算覆盖率
        covered_tokens = set()
        total_tokens = len(content_tokens)
        
        if total_tokens == 0:
            return 0.0
        
        # 提取关键短语
        def extract_key_phrases(skill: str) -> List[str]:
            """从技能点中提取关键短语（2-3个词的组合）"""
            tokens = tokenize(preprocess(skill))
            phrases = []
            # 添加单个关键词
            for token in tokens:
                if len(token) > 2:  # 忽略太短的词
                    phrases.append(token)
            # 添加二元短语
            for i in range(len(tokens) - 1):
                if len(tokens[i]) > 2 and len(tokens[i+1]) > 2:
                    phrases.append(f"{tokens[i]} {tokens[i+1]}")
            # 添加三元短语
            for i in range(len(tokens) - 2):
                if len(tokens[i]) > 2 and len(tokens[i+1]) > 2 and len(tokens[i+2]) > 2:
                    phrases.append(f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")
            return phrases
        
        token_positions = {}
        for i, token in enumerate(content_tokens):
            if token not in token_positions:
                token_positions[token] = []
            token_positions[token].append(i)
        
        for skill in skills:
            key_phrases = extract_key_phrases(skill)
            
            # 检查每个关键短语
            for phrase in key_phrases:
                # 对于单个词
                if ' ' not in phrase:
                    if phrase in token_positions:
                        for pos in token_positions[phrase]:
                            covered_tokens.add(pos)
                # 对于短语（多个词）
                else:
                    phrase_tokens = phrase.split()
                    # 检查短语在原始内容中的连续出现
                    for i in range(len(content_tokens) - len(phrase_tokens) + 1):
                        match = True
                        for j, token in enumerate(phrase_tokens):
                            if content_tokens[i+j] != token:
                                match = False
                                break
                        if match:
                            # 标记短语中所有词的位置
                            for j in range(len(phrase_tokens)):
                                covered_tokens.add(i+j)
        
        # 计算覆盖率
        coverage = len(covered_tokens) / total_tokens
        logger.info(f"计算得到的覆盖率为: {coverage * 100:.2f}%")
        return coverage
    
    def validate_skills(self, structured_content_path: str, skills_data: Dict[str, Any]) -> Tuple[bool, float]:
        # 加载数据
        original_content = self.load_structured_content(structured_content_path)
        skills = self.load_skills(skills_data)
        
        # 计算覆盖率
        coverage = self.calculate_coverage(original_content, skills)
        
        # 判断是否通过
        is_valid = coverage >= self.threshold
        result = "通过" if is_valid else "不通过"
        logger.info(f"技能点验证结果: {result}，覆盖率: {coverage * 100:.2f}%，阈值: {self.threshold * 100}%")
        
        return is_valid, coverage
    
    def generate_refinement_prompt(self, original_skills: Dict[str, Any], coverage: float, structured_content: str) -> str:
        """
        生成用于大模型二次生成的提示词
        
        Args:
            original_skills: 原始生成的技能点数据
            coverage: 当前覆盖率
            structured_content: 原始结构化内容（用于上下文）
            
        Returns:
            用于二次生成的提示词
        """
        # 提取原始技能点
        skills_list = self.load_skills(original_skills)
        skills_text = "\n".join([f"- {skill}" for skill in skills_list])
        
        # 截取部分结构化内容作为上下文（避免token过多）
        context_sample = structured_content[:2000]  # 只取前2000个字符作为上下文
        
        prompt = f"""请重新生成技能点列表，确保其在原始PPT内容中的覆盖率超过90%。

当前覆盖率为: {coverage * 100:.2f}%，未能达到要求的90%。

原始PPT内容片段：
{context_sample}...

请分析以下问题：
1. 现有技能点是否遗漏了PPT中的重要知识点
2. 技能点描述是否足够全面和具体
3. 是否需要增加更多技能点来覆盖PPT的主要内容和核心概念

原始生成的技能点：
{skills_text}

请重新生成更全面的技能点列表，确保能够覆盖PPT中的主要内容。

输出格式要求：
```json
{{
  "skills": [技能点描述列表],
  "groups": [分组信息列表]
}}
```
请确保输出的是有效的JSON格式，并且技能点描述要具体、全面。
"""
        
        return prompt
    
    def call_llm_for_refinement(self, prompt: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        调用大模型进行技能点二次生成
        
        Args:
            prompt: 提示词
            api_key: OpenAI API密钥（可选，如果环境变量中已设置）
            
        Returns:
            生成的技能点数据字典，如果失败则返回None
        """
        try:
            # 设置API密钥
            if api_key:
                openai.api_key = api_key
            elif 'OPENAI_API_KEY' in os.environ:
                openai.api_key = os.environ['OPENAI_API_KEY']
            else:
                logger.error("未找到OpenAI API密钥")
                return None
            
            logger.info("开始调用大模型进行技能点二次生成")
            
            # 调用OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4o",  # 使用与主程序相同的模型
                messages=[
                    {"role": "system", "content": "你是一个专业的教育内容分析助手，擅长从PPT内容中提取全面、准确的学习技能点。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # 提取回复内容
            content = response.choices[0].message.content.strip()
            
            # 提取JSON部分
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                json_content = json_match.group(1)
            else:
                # 尝试直接解析整个内容
                json_content = content
            
            # 解析JSON
            refined_data = json.loads(json_content)
            logger.info("大模型二次生成成功")
            return refined_data
            
        except json.JSONDecodeError as e:
            logger.error(f"解析大模型返回的JSON失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"调用大模型进行二次生成时出错: {str(e)}")
            return None
    
    def validate_and_refine_skills(self, structured_content_path: str, skills_data: Dict[str, Any], 
                                 api_key: Optional[str] = None, max_retries: Optional[int] = None) -> Dict[str, Any]:
        """
        验证技能点覆盖率，如果不达标则触发二次生成，直到达标或达到最大重试次数
        
        Args:
            structured_content_path: 结构化内容文件路径
            skills_data: 初始技能点数据
            api_key: OpenAI API密钥
            max_retries: 最大重试次数（可选，默认使用初始化时的值）
            
        Returns:
            最终的技能点数据（可能是原始数据或经过优化的数据）
        """
        if max_retries is None:
            max_retries = self.max_retries
        
        current_skills = skills_data
        retry_count = 0
        
        while retry_count < max_retries:
            logger.info(f"开始第 {retry_count + 1} 轮验证")
            
            # 执行验证
            is_valid, coverage = self.validate_skills(structured_content_path, current_skills)
            
            if is_valid:
                logger.info("技能点覆盖率达标，无需进一步优化")
                return current_skills
            
            # 如果不达标且还有重试次数，则触发二次生成
            retry_count += 1
            if retry_count > max_retries:
                logger.warning(f"已达到最大重试次数 {max_retries}，返回当前最佳技能点数据")
                break
            
            logger.info(f"覆盖率不达标，开始第 {retry_count} 次二次生成")
            
            # 加载结构化内容用于提示词
            structured_content = self.load_structured_content(structured_content_path)
            
            # 生成优化提示词
            refinement_prompt = self.generate_refinement_prompt(
                current_skills, coverage, structured_content
            )
            
            # 调用大模型进行二次生成
            refined_skills = self.call_llm_for_refinement(refinement_prompt, api_key)
            
            if refined_skills:
                # 更新当前技能点数据
                current_skills = refined_skills
                # 添加间隔避免API限流
                time.sleep(2)
            else:
                logger.error("二次生成失败，保持当前技能点数据")
                break
        
        return current_skills


# 主程序集成接口函数
def validate_skills_coverage(structured_content_path: str, skills_data: Dict[str, Any], 
                           api_key: Optional[str] = None, threshold: float = 0.9,
                           max_retries: int = 2) -> Dict[str, Any]:
    """
    验证技能点覆盖率并在必要时进行优化的便捷函数（供主程序调用）
    
    Args:
        structured_content_path: 结构化内容文件路径
        skills_data: 初始技能点数据
        api_key: OpenAI API密钥
        threshold: 覆盖率阈值
        max_retries: 最大重试次数
        
    Returns:
        经过验证（可能被优化）的技能点数据
    """
    # 创建验证器实例
    validator = SkillValidator(threshold=threshold, max_retries=max_retries)
    
    # 执行验证和优化
    final_skills = validator.validate_and_refine_skills(
        structured_content_path, skills_data, api_key=api_key
    )
    
    return final_skills


def get_coverage_metrics(structured_content_path: str, skills_data: Dict[str, Any]) -> Dict[str, Any]:
    validator = SkillValidator()
    is_valid, coverage = validator.validate_skills(structured_content_path, skills_data)
    
    return {
        "coverage": coverage,
        "is_valid": is_valid,
        "threshold": validator.threshold,
    }
