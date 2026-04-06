import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Text,
  TextInput,
  Textarea,
  Switch,
  Select,
  Group,
  Stack,
  Divider,
  Badge,
  Tooltip,
  Code,
} from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { getConnections } from '../api/connections';
import type { JsonSchemaProperty } from '../types/nodeType';
import type { Connection } from '../api/connections';

/**
 * Field types for rendering
 */
type FieldType = 'text' | 'number' | 'integer' | 'boolean' | 'textarea' | 'connection';

/**
 * Determine field type from JSON schema property
 */
function getFieldType(prop: JsonSchemaProperty, propertyName: string): FieldType {
  // Check for connection type (allOf with $ref to Connection types)
  if (prop.type === 'object' || propertyName === 'connection') {
    const hasAllOfRef = Array.isArray(prop.allOf) && prop.allOf.some(
      (item: any) => item.$ref && item.$ref.includes('Connection')
    );
    if (hasAllOfRef) {
      return 'connection';
    }
  }

  // Check for multiline string
  if (prop.format === 'multiline' || (prop as any).$multiline === true) {
    return 'textarea';
  }

  // Boolean
  if (prop.type === 'boolean') {
    return 'boolean';
  }

  // Number types (render as text to allow Jinja2 templates)
  if (prop.type === 'integer') {
    return 'integer';
  }
  if (prop.type === 'number') {
    return 'number';
  }

  // String (default to text)
  if (prop.type === 'string') {
    return 'text';
  }

  return 'text';
}

/**
 * Get Python-style type label for display
 */
function getTypeLabel(fieldType: FieldType): string {
  switch (fieldType) {
    case 'text':
    case 'textarea':
      return 'str';
    case 'integer':
      return 'int';
    case 'number':
      return 'float';
    case 'boolean':
      return 'bool';
    case 'connection':
      return 'Connection';
    default:
      return fieldType;
  }
}

/**
 * Render a single form field based on its type
 */
function FormField({
  propertyName,
  property,
  value,
  onChange,
  isRequired,
  connections,
  defs,
}: {
  propertyName: string;
  property: JsonSchemaProperty;
  value: unknown;
  onChange: (value: unknown) => void;
  isRequired: boolean;
  connections: Connection[];
  defs: Record<string, JsonSchemaProperty>;
}) {
  const fieldType = getFieldType(property, propertyName);

  // Use propertyName (snake_case) as the primary label, title as fallback for description
  const label = propertyName;
  const description = property.description;

  // Determine human-readable type label
  const typeLabel = fieldType === 'connection'
    ? 'Connection'
    : fieldType === 'textarea'
      ? 'str (multiline)'
      : getTypeLabel(fieldType);

  const infoIcon = description ? (
    <Tooltip label={description} multiline withArrow w={200}>
      <IconInfoCircle size={14} style={{ marginLeft: 4, cursor: 'help', flexShrink: 0 }} />
    </Tooltip>
  ) : null;

  // Handle connection fields (dropdown to select from existing connections)
  if (fieldType === 'connection') {
    // Extract connection type from $defs
    const allOf = (property as any).allOf;
    let connectionClassName: string | undefined;
    let connectionType: string | undefined;
    
    if (Array.isArray(allOf)) {
      const refItem = allOf.find((item: any) => item.$ref);
      if (refItem) {
        // Extract type name from $ref like "#/$defs/PostgresConnection"
        const refPath = refItem.$ref;
        const typeName = refPath.split('/').pop();
        connectionClassName = typeName; // e.g., "PostgresConnection"
        const def = defs[typeName];
        if (def && (def as any)['x-connection-type']) {
          connectionType = (def as any)['x-connection-type'];
        }
      }
    }

    const filteredConnections = connectionType
      ? connections.filter((c) => c.connection_type === connectionType)
      : connections;

    // Value is a connection ID
    const currentValue = value as string | undefined;

    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}
            {isRequired && (
              <Text span c="red" fw={700} ml={4}>
                *
              </Text>
            )}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">
            {connectionClassName || 'Connection'}
          </Badge>
        </Group>
        <Select
          value={currentValue || null}
          onChange={(val) => onChange(val)}
          placeholder="Select a connection..."
          data={filteredConnections.map((conn) => ({
            value: conn.id,
            label: `${conn.name} (${conn.connection_type})`,
          }))}
          size="sm"
          clearable
          disabled={filteredConnections.length === 0}
        />
        {filteredConnections.length === 0 && (
          <Text size="xs" c="dimmed" mt={4}>
            No connections available. Create a connection in the Connections page.
          </Text>
        )}
        {description && (
          <Text size="xs" c="dimmed" mt={4}>
            {description}
          </Text>
        )}
      </Box>
    );
  }

  // Boolean field (Switch)
  if (fieldType === 'boolean') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}
            {isRequired && (
              <Text span c="red" fw={700} ml={4}>
                *
              </Text>
            )}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">
            {typeLabel}
          </Badge>
        </Group>
        <Switch
          checked={Boolean(value)}
          onChange={(e) => onChange(e.currentTarget.checked)}
          label={value ? 'Yes' : 'No'}
          size="md"
        />
      </Box>
    );
  }

  // Integer/Number field (use TextInput to allow Jinja2 templates)
  if (fieldType === 'integer' || fieldType === 'number') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}
            {isRequired && (
              <Text span c="red" fw={700} ml={4}>
                *
              </Text>
            )}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">
            {typeLabel}
          </Badge>
        </Group>
        <TextInput
          value={value !== undefined ? String(value) : ''}
          onChange={(e) => onChange(e.currentTarget.value)}
          placeholder={property.default?.toString()}
          size="sm"
        />
      </Box>
    );
  }

  // Textarea field (multiline string)
  if (fieldType === 'textarea') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}
            {isRequired && (
              <Text span c="red" fw={700} ml={4}>
                *
              </Text>
            )}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">
            {typeLabel}
          </Badge>
        </Group>
        <Textarea
          value={(value as string) || ''}
          onChange={(e) => onChange(e.currentTarget.value)}
          placeholder={property.default?.toString()}
          autosize
          minRows={3}
          maxRows={10}
          size="sm"
        />
      </Box>
    );
  }

  // Default text field
  return (
    <Box mb="md">
      <Group wrap="nowrap" mb={4} gap={4}>
        <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
          {label}
          {isRequired && (
            <Text span c="red" fw={700} ml={4}>
              *
            </Text>
          )}
        </Text>
        {infoIcon}
        <Badge size="xs" variant="light">
          {typeLabel}
        </Badge>
      </Group>
      <TextInput
        value={(value as string) || ''}
        onChange={(e) => onChange(e.currentTarget.value)}
        placeholder={property.default?.toString()}
        size="sm"
      />
    </Box>
  );
}

/**
 * Get a human-readable type label from JSON schema type
 */
function getTypeLabelFromSchema(schemaType: string): string {
  const typeMap: Record<string, string> = {
    string: 'str',
    integer: 'int',
    number: 'float',
    boolean: 'bool',
    object: 'object',
    array: 'list',
  };
  return typeMap[schemaType] || schemaType;
}

/**
 * Node Parameters Form component
 * Dynamically generates form UI from JSON Schema
 */
export function NodeParamsForm({
  inputSchema,
  outputSchema,
  config,
  onChange,
}: {
  inputSchema: {
    properties: Record<string, JsonSchemaProperty>;
    required?: string[];
    $defs?: Record<string, JsonSchemaProperty>;
  } | null;
  outputSchema?: {
    properties: Record<string, JsonSchemaProperty>;
    required?: string[];
  } | null;
  config: Record<string, unknown>;
  onChange: (updatedConfig: Record<string, unknown>) => void;
}) {
  const [connections, setConnections] = useState<Connection[]>([]);

  // Fetch available connections on mount
  useEffect(() => {
    let mounted = true;
    getConnections()
      .then((conns) => {
        if (mounted) setConnections(conns);
      })
      .catch((err) => {
        console.error('Failed to load connections:', err);
      });
    return () => { mounted = false; };
  }, []);

  const handleFieldChange = useCallback(
    (fieldName: string, value: unknown) => {
      const updatedConfig = { ...config, [fieldName]: value };
      onChange(updatedConfig);
    },
    [config, onChange]
  );

  const properties = useMemo(() => {
    if (!inputSchema?.properties) {
      return {};
    }
    return inputSchema.properties;
  }, [inputSchema]);

  const requiredFields = useMemo(() => {
    return new Set(inputSchema?.required || []);
  }, [inputSchema]);

  const defs = useMemo(() => {
    return inputSchema?.$defs || {};
  }, [inputSchema]);

  if (!inputSchema || Object.keys(properties).length === 0) {
    return (
      <Box mt="md">
        <Text c="dimmed" size="sm">
          No parameters to configure for this node type.
        </Text>
      </Box>
    );
  }

  return (
    <Box mt="md">
      <Stack gap="xs">
        {Object.entries(properties).map(([fieldName, property], index, entries) => {
          const isRequired = requiredFields.has(fieldName);
          const currentValue =
            config[fieldName] !== undefined ? config[fieldName] : property.default;
          const isLast = index === entries.length - 1;

          return (
            <Box key={fieldName}>
              <FormField
                propertyName={fieldName}
                property={property}
                value={currentValue}
                onChange={(value) => handleFieldChange(fieldName, value)}
                isRequired={isRequired}
                connections={connections}
                defs={defs}
              />
              {!isLast && <Divider mt="xs" />}
            </Box>
          );
        })}
      </Stack>

      {/* Output variables */}
      {outputSchema?.properties && Object.keys(outputSchema.properties).length > 0 && (
        <Box mt="md">
          <Divider mb="xs" label="Выходные переменные" labelPosition="center" />
          <Stack gap={6}>
            {Object.entries(outputSchema.properties).map(([paramName, propSchema]) => {
              const schema = propSchema as Record<string, unknown>;
              const typeLabel = getTypeLabelFromSchema((schema.type as string) || 'unknown');

              return (
                <Group key={paramName} gap="xs" wrap="nowrap">
                  <Code>{paramName}</Code>
                  <Text size="xs" c="dimmed">
                    {typeLabel}
                  </Text>
                  {schema.description && (
                    <Tooltip label={schema.description} withArrow>
                      <IconInfoCircle size={14} style={{ cursor: 'pointer', color: '#868e96' }} />
                    </Tooltip>
                  )}
                </Group>
              );
            })}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
