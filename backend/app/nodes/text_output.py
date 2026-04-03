"""Text output node - Hello World implementation."""

import logging

from app.nodes.base import BaseNode, NodeContext, NodeResult
from app.nodes.registry import NodeRegistry


@NodeRegistry.register
class TextOutputNode(BaseNode):
    """Simple text output node for testing.

    Outputs a text message, optionally using template resolution
    from upstream node outputs.

    Configuration:
        message: The text message to output (can contain {{ node_id.output }} templates)

    Outputs:
        text: The output message string
    """

    node_type = "text_output"

    def execute(
        self, context: NodeContext, logger: logging.Logger | None = None
    ) -> NodeResult:
        """Execute the text output node.

        Args:
            context: Execution context with node configuration
            logger: Optional logger for streaming logs

        Returns:
            NodeResult with the text output
        """
        # Use provided logger or standard logging
        log_func = logger.info if logger else logging.info

        # Get node configuration from context
        config = context.pipeline_params.get("node_config", {})
        message = config.get("message", "Hello, World!")

        log_func(f"Starting text output node with message template: {message}")

        # Resolve templates in the message
        resolved_message = self._resolve_templates(message, context)

        log_func(f"Resolved message: {resolved_message}")
        log_func("Text output node completed successfully")

        return NodeResult(
            success=True,
            outputs={"text": resolved_message},
            logs=[
                f"Starting text output node with message template: {message}",
                f"Resolved message: {resolved_message}",
                "Text output node completed successfully",
            ],
        )

    def _resolve_templates(self, message: str, context: NodeContext) -> str:
        """Resolve {{ node_id.output_name }} templates in the message.

        Args:
            message: Message potentially containing template references
            context: Execution context with upstream outputs

        Returns:
            Message with all references resolved
        """
        import re

        def replace_ref(match: re.Match) -> str:
            ref = match.group(1)
            parts = ref.split(".", 1)
            if len(parts) != 2:
                return match.group(0)

            node_id, output_name = parts
            value = context.get_output(node_id, output_name)
            if value is not None:
                return str(value)
            return match.group(0)

        return re.sub(r"\{\{\s*(.+?)\s*\}\}", replace_ref, message)

    def validate_config(self, config: dict) -> None:
        """Validate node configuration.

        Args:
            config: Node configuration from the graph definition

        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")

        message = config.get("message")
        if message is not None and not isinstance(message, str):
            raise ValueError("Message must be a string")
