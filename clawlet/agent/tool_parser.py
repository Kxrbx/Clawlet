"""Tool call parser for extracting tool calls from LLM responses."""

import json
import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class ParsedToolCall:
    """Represents a parsed tool call."""
    id: str
    name: str
    arguments: dict


class ToolCallParser:
    """Parses tool calls from LLM response content.
    
    Supports three formats:
    1. JSON blocks: ```json{"name": "...", "arguments": {...}}```
    2. XML-style: <tool_call name="..." arguments='{...}'/>
    3. Simple key-value: tool: name | arguments: {...}
    """
    
    # Pattern 1: JSON blocks ```json ... ``` or ``` ... ``` blocks containing JSON
    JSON_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', re.IGNORECASE)
    
    # Pattern 2: XML-style <tool_call name="..." arguments='{...}'/>
    XML_PATTERN = re.compile(
        r'<tool_call\s+name="([^"]+)"\s+arguments=\'(\{[^\']*\}|\[[^\']*\])\'\s*/?>'
    )
    
    # Pattern 3: Simple key-value format
    SIMPLE_PATTERN = re.compile(
        r'tool[:\s]+([a-zA-Z_][a-zA-Z0-9_]*)[\s\n]+arguments?[:\s]+(\{[^}]+\}|\[[^\]]+\])',
        re.IGNORECASE
    )
    
    def parse(self, content: str) -> list[ParsedToolCall]:
        """Parse all tool calls from content.
        
        Args:
            content: The LLM response content to parse
            
        Returns:
            List of ParsedToolCall objects
        """
        tool_calls = []
        
        # Try each pattern in order
        tool_calls.extend(self._parse_json_blocks(content))
        tool_calls.extend(self._parse_xml_format(content))
        tool_calls.extend(self._parse_simple_format(content))
        
        if tool_calls:
            logger.info(f"Extracted {len(tool_calls)} tool call(s)")
        
        return tool_calls
    
    def _parse_json_blocks(self, content: str) -> list[ParsedToolCall]:
        """Parse JSON blocks from content.
        
        Handles:
        - Single tool call: {"name": "...", "arguments": {...}}
        - Array of tool calls: [{"name": "...", "arguments": {...}}, ...]
        """
        tool_calls = []
        
        json_matches = self.JSON_BLOCK_PATTERN.findall(content)
        
        for i, json_str in enumerate(json_matches):
            json_str = json_str.strip()
            if not json_str:
                continue
            try:
                data = json.loads(json_str)
                
                # Handle single tool call object
                if isinstance(data, dict) and "name" in data:
                    arguments = data.get("arguments", data.get("parameters", {}))
                    if not isinstance(arguments, dict):
                        arguments = {"value": arguments}
                    tool_calls.append(ParsedToolCall(
                        id=f"call_json_{i}",
                        name=data["name"],
                        arguments=arguments,
                    ))
                # Handle array of tool calls
                elif isinstance(data, list):
                    for j, item in enumerate(data):
                        if isinstance(item, dict) and "name" in item:
                            arguments = item.get("arguments", item.get("parameters", {}))
                            if not isinstance(arguments, dict):
                                arguments = {"value": arguments}
                            tool_calls.append(ParsedToolCall(
                                id=f"call_json_{i}_{j}",
                                name=item["name"],
                                arguments=arguments,
                            ))
            except json.JSONDecodeError:
                pass  # Not valid JSON, try other formats
        
        return tool_calls
    
    def _parse_xml_format(self, content: str) -> list[ParsedToolCall]:
        """Parse XML-style tool calls from content.
        
        Format: <tool_call name="..." arguments='{...}'/>
        """
        tool_calls = []
        
        try:
            matches = self.XML_PATTERN.findall(content)
            
            for i, (name, args_str) in enumerate(matches):
                try:
                    args = json.loads(args_str)
                    if isinstance(args, dict):
                        tool_calls.append(ParsedToolCall(
                            id=f"call_xml_{i}",
                            name=name,
                            arguments=args,
                        ))
                    else:
                        # Arguments is a list or primitive, wrap in dict
                        tool_calls.append(ParsedToolCall(
                            id=f"call_xml_{i}",
                            name=name,
                            arguments={"value": args},
                        ))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse tool arguments for {name}: {e}")
        except re.error as e:
            logger.error(f"Regex error in XML tool call extraction: {e}")
        
        return tool_calls
    
    def _parse_simple_format(self, content: str) -> list[ParsedToolCall]:
        """Parse simple key-value format from content.
        
        Format: tool: name | arguments: {...}
        """
        tool_calls = []
        
        try:
            simple_matches = self.SIMPLE_PATTERN.findall(content)
            for i, (name, args_str) in enumerate(simple_matches):
                try:
                    args = json.loads(args_str)
                    tool_calls.append(ParsedToolCall(
                        id=f"call_simple_{i}",
                        name=name.strip(),
                        arguments=args if isinstance(args, dict) else {"value": args},
                    ))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse simple format for {name}: {e}")
        except re.error as e:
            logger.error(f"Regex error in simple tool call extraction: {e}")
        
        return tool_calls
