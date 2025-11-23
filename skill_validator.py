#!/usr/bin/env python
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
import re
import time
import os
import yaml
from pathlib import Path
from client import openai_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SkillValidator:    
    def __init__(self, threshold: float = 0.9):
        self.threshold = threshold
        logger.info(f"技能点验证器初始化完成，覆盖率阈值设置为 {threshold * 100}%")
    
    def load_md_content(self, md_path: str) -> str:
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"成功加载markdown文件: {md_path}")
            return content
        except Exception as e:
            logger.error(f"加载markdown文件失败: {str(e)}")
            return ""
    
    def load_skills_from_yaml(self, yaml_path: str) -> List[str]:
        skills_list = []
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                skills = data.get('skills', [])
                for skill in skills:
                    if isinstance(skill, dict):
                        for value in skill.values():
                            skills_list.append(str(value))
                    elif isinstance(skill, str):
                        skills_list.append(skill)
            logger.info(f"成功从YAML文件提取 {len(skills_list)} 个技能点")
        except Exception as e:
            logger.error(f"加载技能点YAML文件失败: {str(e)}")
        return skills_list
    
    def calculate_coverage(self, md_content: str, skills: List[str]) -> float:
        if not md_content or not skills:
            logger.warning("Markdown内容或技能点列表为空，无法计算覆盖率")
            return 0.0
        
        skills_text = "\n".join([f"- {skill}" for skill in skills])
        
        max_content_length = 2000
        if len(md_content) > max_content_length:
            md_content = md_content[:max_content_length] + "\n[内容过长，已截断]"
        
        prompt = f"""你是一位专业的教育评估专家，请评估以下markdown内容（代表PPT内容）是否被给定的技能点列表完全覆盖。

        请分析每一页或每个重要的内容块，判断它们是否至少被一个技能点覆盖，并计算总体覆盖率。

        覆盖率评估标准：
        1. 将markdown内容划分为逻辑上独立的内容块（如不同的页面、主题或章节）
        2. 对于每个重要的内容块，如果它被至少一个技能点直接或间接覆盖（即该技能点要求掌握这部分内容），则该内容块的覆盖率为100%
        3. 如果内容块的部分内容被覆盖，则覆盖率为50%
        4. 如果内容块完全没有被任何技能点覆盖，则覆盖率为0%

        请按照以下格式输出结果：
        ```json
        {
        "content_blocks": [
            {"block_summary": "内容块简要描述", "covered": true/false, "covering_skills": ["覆盖该内容的技能点索引或内容"]},
            // 其他内容块...
        ],
        "overall_coverage": 总体覆盖率(0.0-1.0)
        }
        ```

        Markdown内容：
        ```
        {md_content}
        ```

        技能点列表：
        {skills_text}
        """
        
        try:
            logger.info("调用大模型计算技能点覆盖率...")
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "你是一位专业的教育评估专家，擅长评估学习内容的覆盖率。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            response_content = response.choices[0].message.content
            
            # 提取JSON响应
            json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
            if json_match:
                try:
                    coverage_data = json.loads(json_match.group(1))
                    overall_coverage = coverage_data.get('overall_coverage', 0.0)
                    
                    # 记录未覆盖的内容块
                    uncovered_blocks = []
                    if 'content_blocks' in coverage_data:
                        uncovered_blocks = [block for block in coverage_data['content_blocks'] if not block.get('covered', True)]
                        if uncovered_blocks:
                            logger.warning(f"发现{len(uncovered_blocks)}个未被技能点覆盖的重要内容块")
                            for i, block in enumerate(uncovered_blocks[:3]):  # 只记录前3个未覆盖的内容块
                                logger.warning(f"未覆盖内容块{i+1}: {block.get('block_summary', '未提供描述')}")
                    
                    logger.info(f"大模型计算的总体覆盖率为: {overall_coverage * 100:.2f}%")
                    return overall_coverage
                except json.JSONDecodeError:
                    logger.error("无法解析大模型返回的JSON格式")
                    return 0.0
            else:
                logger.error("无法从大模型响应中提取有效的JSON")
                return 0.0
                
        except Exception as e:
            logger.error(f"调用大模型计算覆盖率时出错: {str(e)}")
            return 0.0
    
# 主程序集成接口函数
def validate_skills_coverage(yaml_path: str, md_path: str, threshold: float = 0.9) -> Tuple[bool, float]:
    
    validator = SkillValidator(threshold=threshold)
    
    coverage = validator.calculate_coverage(yaml_path, md_path)
    is_valid = coverage >= threshold
    
    return is_valid, coverage