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
    
    Supports four formats:
    1. JSON blocks: ```json{"name": "...", "arguments": {...}}```
    2. XML-style: <tool_call name="..." arguments='{...}'/>
    3. Simple key-value: tool: name | arguments: {...}
    4. MCP-like format:
       <tool_call>
       <function=tool_name>
       <parameter=key>value</parameter>
       </tool_call>
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
    
    # Pattern 4: MCP-like format: <tool_call><function=NAME>...<parameter=KEY>VALUE</parameter>...</tool_call>
    MCP_PATTERN = re.compile(
        r'<tool_call>\s*<function=([a-zA-Z_][a-zA-Z0-9_]*)>\s*([\s\S]*?)\s*</tool_call>',
        re.IGNORECASE
    )
    MCP_PARAM_PATTERN = re.compile(
        r'<parameter=([a-zA-Z_][a-zA-Z0-9_]*)\s*>([^<]*)\s*</parameter>',
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
        json_calls = self._parse_json_blocks(content)
        xml_calls = self._parse_xml_format(content)
        simple_calls = self._parse_simple_format(content)
        mcp_calls = self._parse_mcp_format(content)
        
        tool_calls.extend(json_calls)
        tool_calls.extend(xml_calls)
        tool_calls.extend(simple_calls)
        tool_calls.extend(mcp_calls)
        
        # DEBUG: Log which patterns matched
        if json_calls or xml_calls or simple_calls or mcp_calls:
            logger.warning(f"[DIAGNOSTIC] Tool parser matches - JSON: {len(json_calls)}, XML: {len(xml_calls)}, Simple: {len(simple_calls)}, MCP: {len(mcp_calls)}")
            logger.debug(f"[DIAGNOSTIC] Raw content sample: {content[:300]}...")
        
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
    
    def _parse_mcp_format(self, content: str) -> list[ParsedToolCall]:
        """Parse MCP-like tool calls from content.
        
        Format:
        <tool_call>
        <function=tool_name>
        <parameter=key>value</parameter>
        </tool_call>
        """
        tool_calls = []
        
        try:
            # Find all tool_call blocks
            mcp_matches = self.MCP_PATTERN.findall(content)
            
            for i, match in enumerate(mcp_matches):
                # New pattern: 2 groups (func_name, params_section)
                if len(match) == 2:
                    func_name, params_section = match
                    func_name = func_name.strip()
                else:
                    # Old pattern: 3 groups (func_name, func_content, params_content)
                    func_name, func_content, params_section = match[:3]
                    func_name = func_name.strip()
                
                # Extract parameters from the params section
                arguments = {}
                param_matches = self.MCP_PARAM_PATTERN.findall(params_section)
                
                for param_name, param_value in param_matches:
                    param_name = param_name.strip()
                    param_value = param_value.strip()
                    
                    # Try to parse as JSON (for numbers, booleans, etc.)
                    try:
                        # Check if it's a JSON primitive
                        if param_value.lower() in ('true', 'false'):
                            param_value = param_value.lower() == 'true'
                        elif param_value.isdigit():
                            param_value = int(param_value)
                        elif param_value.replace('.', '', 1).isdigit():
                            param_value = float(param_value)
                    except (ValueError, AttributeError):
                        pass  # Keep as string
                    
                    arguments[param_name] = param_value
                
                tool_calls.append(ParsedToolCall(
                    id=f"call_mcp_{i}",
                    name=func_name,
                    arguments=arguments,
                ))
                logger.debug(f"Parsed MCP tool call: {func_name} with args {arguments}")
                
        except re.error as e:
            logger.error(f"Regex error in MCP tool call extraction: {e}")
        
        return tool_calls
