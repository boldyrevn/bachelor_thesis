import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Text,
  TextInput,
  Textarea,
  Select,
  Group,
  Stack,
  Divider,
  Badge,
  Tooltip,
  Code,
  Button,
  ActionIcon,
  NumberInput,
  SegmentedControl,
  ScrollArea,
} from '@mantine/core';
import { DateInput, DateTimePicker } from '@mantine/dates';
import { IconInfoCircle, IconPlus, IconTrash, IconArrowUp, IconArrowDown } from '@tabler/icons-react';
import dayjs from 'dayjs';
import { getConnections } from '../api/connections';
import type { JsonSchemaProperty } from '../types/nodeType';
import type { Connection } from '../api/connections';

// ─── Type detection ────────────────────────────────────────────────────────

/**
 * Field types for rendering
 */
type FieldType =
  | 'text'
  | 'number'
  | 'integer'
  | 'boolean'
  | 'optionalBoolean'
  | 'textarea'
  | 'date'
  | 'datetime'
  | 'connection'
  | 'dict'
  | 'list'
  | 'union';

/**
 * Resolve a $ref to its definition in $defs
 */
function resolveRef(
  schema: Record<string, unknown>,
  defs: Record<string, JsonSchemaProperty>,
): Record<string, unknown> | null {
  const ref = schema.$ref as string | undefined;
  if (ref?.startsWith('#/$defs/')) {
    const defName = ref.replace('#/$defs/', '');
    return (defs[defName] as Record<string, unknown>) || null;
  }
  return null;
}

/**
 * Determine field type from JSON schema property
 */
function getFieldType(
  prop: JsonSchemaProperty,
  _propertyName: string,
  defs: Record<string, JsonSchemaProperty>,
): FieldType {
  const resolved = resolveRef(prop as Record<string, unknown>, defs);
  const schema = (resolved || prop) as Record<string, unknown>;

  if (Array.isArray(schema.allOf)) {
    const hasConnectionRef = schema.allOf.some(
      (item: any) => item.$ref && item.$ref.includes('Connection'),
    );
    if (hasConnectionRef) return 'connection';
  }

  if (schema['x-connection-type']) return 'connection';

  const format = schema.format as string | undefined;
  if (format === 'multiline') return 'textarea';
  if (format === 'date') return 'date';
  if (format === 'date-time') return 'datetime';

  if (schema.type === 'object' && schema.additionalProperties) return 'dict';
  if (schema.type === 'array' && schema.items) return 'list';

  if (schema.anyOf && Array.isArray(schema.anyOf)) {
    const nonNull = (schema.anyOf as Record<string, unknown>[]).filter(
      (s) => s.type !== 'null',
    );
    if (nonNull.length > 1) return 'union';
    if (nonNull.length === 1) {
      const inner = nonNull[0];
      if (inner.format === 'multiline') return 'textarea';
      if (inner.format === 'date') return 'date';
      if (inner.format === 'date-time') return 'datetime';
      if (inner.type === 'object' && inner.additionalProperties) return 'dict';
      if (inner.type === 'array' && inner.items) return 'list';
      if (inner.type === 'boolean') return 'optionalBoolean';
      if (inner.type === 'integer') return 'integer';
      if (inner.type === 'number') return 'number';
      if (inner.type === 'string') return 'text';
    }
  }

  if (schema.type === 'boolean') return 'boolean';
  if (schema.type === 'integer') return 'integer';
  if (schema.type === 'number') return 'number';
  if (schema.type === 'string') return 'text';

  return 'text';
}

/**
 * Get Python-style type label for a schema.
 * For Optional[T] (anyOf with one non-null type), returns just the inner type label
 * since optionality is already conveyed by the absence of the red asterisk.
 */
function getTypeLabel(schema: Record<string, unknown>, defs: Record<string, JsonSchemaProperty>): string {
  const resolved = resolveRef(schema, defs);
  const s = (resolved || schema) as Record<string, unknown>;

  if (Array.isArray(s.allOf)) {
    for (const item of s.allOf as any[]) {
      if (item.$ref?.startsWith('#/$defs/')) {
        return item.$ref.split('/').pop() || 'Connection';
      }
    }
  }
  if (s['x-connection-type']) return `${s['x-connection-type']} Connection`;

  const format = s.format as string | undefined;
  if (format === 'multiline') return 'str (multiline)';
  if (format === 'date') return 'date';
  if (format === 'date-time') return 'datetime';

  if (s.type === 'object' && s.additionalProperties) {
    const valueSchema = s.additionalProperties as Record<string, unknown>;
    return `dict[str, ${getTypeLabel(valueSchema, defs)}]`;
  }

  if (s.type === 'array' && s.items) {
    const itemSchema = s.items as Record<string, unknown>;
    return `list[${getTypeLabel(itemSchema, defs)}]`;
  }

  // anyOf: handle Union and Optional
  if (s.anyOf && Array.isArray(s.anyOf)) {
    const nonNull = (s.anyOf as Record<string, unknown>[]).filter(
      (item) => item.type !== 'null',
    );
    if (nonNull.length === 0) return 'null';
    if (nonNull.length === 1) {
      // Optional[T] — return just the inner type (optionality shown by no asterisk)
      return getTypeLabel(nonNull[0], defs);
    }
    // Union[A, B, ...] — show full union
    const labels = nonNull.map((item) => getTypeLabel(item, defs));
    return `Union[${labels.join(', ')}]`;
  }

  const typeMap: Record<string, string> = {
    string: 'str',
    integer: 'int',
    number: 'float',
    boolean: 'bool',
    object: 'dict',
    array: 'list',
  };
  return (typeMap[s.type as string] || (s.type as string) || 'unknown') as string;
}

// ─── Typed value input for dict values and list items ──────────────────────

function PrimitiveValueInput({
  value,
  onChange,
  schema,
  defs,
}: {
  value: unknown;
  onChange: (v: unknown) => void;
  schema: Record<string, unknown>;
  defs: Record<string, JsonSchemaProperty>;
}) {
  const resolved = resolveRef(schema, defs);
  const s = (resolved || schema) as Record<string, unknown>;
  const format = s.format as string | undefined;

  if (s.type === 'boolean') {
    return (
      <Select
        value={value === true ? 'true' : value === false ? 'false' : ''}
        onChange={(v) => onChange(v === 'true' ? true : v === 'false' ? false : null)}
        data={[
          { value: 'true', label: 'True' },
          { value: 'false', label: 'False' },
        ]}
        size="xs"
      />
    );
  }

  if (s.type === 'integer') {
    return (
      <NumberInput
        value={value !== undefined && value !== null ? Number(value) : undefined}
        onChange={(v) => onChange(v !== '' && v !== null && v !== undefined ? Number(v) : null)}
        step={1}
        allowDecimal={false}
        hideControls
        size="xs"
      />
    );
  }

  if (s.type === 'number') {
    return (
      <NumberInput
        value={value !== undefined && value !== null ? Number(value) : undefined}
        onChange={(v) => onChange(v !== '' && v !== null && v !== undefined ? Number(v) : null)}
        step={0.1}
        hideControls
        size="xs"
      />
    );
  }

  if (format === 'date') {
    const dateValue = value ? dayjs(value as string).toDate() : null;
    return (
      <DateInput
        value={dateValue}
        onChange={(d) => {
          if (d) {
            onChange(dayjs(d).format('YYYY-MM-DD'));
          } else {
            onChange(null);
          }
        }}
        size="xs"
        valueFormat="YYYY-MM-DD"
      />
    );
  }

  if (format === 'date-time') {
    const dateValue = value ? dayjs(value as string).toDate() : null;
    return (
      <DateTimePicker
        value={dateValue}
        onChange={(d) => {
          if (d) {
            onChange(dayjs(d).utc().format());
          } else {
            onChange(null);
          }
        }}
        size="xs"
        valueFormat="YYYY-MM-DD HH:mm:ss"
      />
    );
  }

  if (format === 'multiline') {
    return (
      <Textarea
        value={(value as string) || ''}
        onChange={(e) => onChange(e.currentTarget.value)}
        size="xs"
        autosize
        minRows={2}
        maxRows={5}
      />
    );
  }

  return (
    <TextInput
      value={(value as string) || ''}
      onChange={(e) => onChange(e.currentTarget.value)}
      size="xs"
    />
  );
}

// ─── Dict field ────────────────────────────────────────────────────────────

function DictField({
  label,
  typeLabel,
  value,
  onChange,
  isRequired,
  infoIcon,
  additionalProperties,
  defs,
}: {
  label: string;
  typeLabel: string;
  value: unknown;
  onChange: (v: unknown) => void;
  isRequired: boolean;
  infoIcon: React.ReactNode;
  additionalProperties: Record<string, unknown>;
  defs: Record<string, JsonSchemaProperty>;
}) {
  const entries = useMemo(() => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return Object.entries(value as Record<string, unknown>);
    }
    return [] as [string, unknown][];
  }, [value]);

  const addEntry = () => {
    const newEntries = { ...(value as Record<string, unknown>) || {}, '': '' };
    onChange(newEntries);
  };

  const updateKey = (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return;
    const obj = { ...(value as Record<string, unknown>) };
    const val = obj[oldKey];
    delete obj[oldKey];
    obj[newKey] = val;
    onChange(obj);
  };

  const updateVal = (key: string, newVal: unknown) => {
    const obj = { ...(value as Record<string, unknown>) };
    obj[key] = newVal;
    onChange(obj);
  };

  const removeEntry = (key: string) => {
    const obj = { ...(value as Record<string, unknown>) };
    delete obj[key];
    onChange(obj);
  };

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
      <Stack gap={4}>
        {entries.map(([key, val], index) => (
          <Group key={index} gap="xs" wrap="nowrap" align="flex-start">
            <TextInput
              value={key}
              onChange={(e) => updateKey(key, e.currentTarget.value)}
              placeholder="key"
              size="xs"
              style={{ flex: '0 0 120px' }}
            />
            <PrimitiveValueInput
              value={val}
              onChange={(v) => updateVal(key, v)}
              schema={additionalProperties}
              defs={defs}
            />
            <ActionIcon color="red" variant="subtle" size="sm" onClick={() => removeEntry(key)}>
              <IconTrash size={14} />
            </ActionIcon>
          </Group>
        ))}
        <Button variant="subtle" size="compact-xs" onClick={addEntry} leftSection={<IconPlus size={14} />}>
          Add entry
        </Button>
      </Stack>
    </Box>
  );
}

// ─── List field ────────────────────────────────────────────────────────────

function ListField({
  label,
  typeLabel,
  value,
  onChange,
  isRequired,
  infoIcon,
  itemsSchema,
  defs,
}: {
  label: string;
  typeLabel: string;
  value: unknown;
  onChange: (v: unknown) => void;
  isRequired: boolean;
  infoIcon: React.ReactNode;
  itemsSchema: Record<string, unknown>;
  defs: Record<string, JsonSchemaProperty>;
}) {
  const items = useMemo(() => {
    if (Array.isArray(value)) return value;
    return [];
  }, [value]);

  const addItem = () => {
    onChange([...items, '']);
  };

  const updateItem = (index: number, newVal: unknown) => {
    const newItems = [...items];
    newItems[index] = newVal;
    onChange(newItems);
  };

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const moveItem = (index: number, direction: -1 | 1) => {
    const newIdx = index + direction;
    if (newIdx < 0 || newIdx >= items.length) return;
    const newItems = [...items];
    [newItems[index], newItems[newIdx]] = [newItems[newIdx], newItems[index]];
    onChange(newItems);
  };

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
      <Stack gap={4}>
        {items.map((item, index) => (
          <Group key={index} gap="xs" wrap="nowrap" align="flex-start">
            <Text size="xs" c="dimmed" style={{ width: 20, textAlign: 'center', paddingTop: 6 }}>
              {index}
            </Text>
            <Box style={{ flex: 1 }}>
              <PrimitiveValueInput
                value={item}
                onChange={(v) => updateItem(index, v)}
                schema={itemsSchema}
                defs={defs}
              />
            </Box>
            <ActionIcon
              variant="subtle"
              size="sm"
              onClick={() => moveItem(index, -1)}
              disabled={index === 0}
            >
              <IconArrowUp size={14} />
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              size="sm"
              onClick={() => moveItem(index, 1)}
              disabled={index === items.length - 1}
            >
              <IconArrowDown size={14} />
            </ActionIcon>
            <ActionIcon color="red" variant="subtle" size="sm" onClick={() => removeItem(index)}>
              <IconTrash size={14} />
            </ActionIcon>
          </Group>
        ))}
        <Button variant="subtle" size="compact-xs" onClick={addItem} leftSection={<IconPlus size={14} />}>
          Add item
        </Button>
      </Stack>
    </Box>
  );
}

// ─── Union field ───────────────────────────────────────────────────────────

function UnionField({
  label,
  typeLabel,
  value,
  onChange,
  isRequired,
  infoIcon,
  anyOf,
  defs,
}: {
  label: string;
  typeLabel: string;
  value: unknown;
  onChange: (v: unknown) => void;
  isRequired: boolean;
  infoIcon: React.ReactNode;
  anyOf: Record<string, unknown>[];
  defs: Record<string, JsonSchemaProperty>;
}) {
  const hasNull = anyOf.some((s) => s.type === 'null');
  const nonNull = anyOf.filter((s) => s.type !== 'null');

  // Compute initial mode from current value (only on mount)
  // mode can be 'null' or a type index (0-based within nonNull)
  const getInitialMode = (): 'null' | number => {
    if (value === null || value === undefined) return hasNull ? 'null' : 0;
    for (let i = 0; i < nonNull.length; i++) {
      const s = nonNull[i];
      if (s.type === 'string' && typeof value === 'string') return i;
      if (s.type === 'integer' && typeof value === 'number' && Number.isInteger(value)) return i;
      if (s.type === 'number' && typeof value === 'number') return i;
      if (s.type === 'boolean' && typeof value === 'boolean') return i;
      if (s.type === 'object' && typeof value === 'object' && !Array.isArray(value)) return i;
      if (s.type === 'array' && Array.isArray(value)) return i;
    }
    return 0;
  };

  const [mode, setMode] = useState<'null' | number>(getInitialMode);
  const isNullMode = mode === 'null';
  const schema = typeof mode === 'number' ? nonNull[mode] || nonNull[0] : null;

  // Build segmented control data
  const segmentedData = [
    ...nonNull.map((s, i) => ({
      value: `type_${i}`,
      label: getTypeLabel(s, defs),
    })),
    ...(hasNull ? [{ value: 'null', label: 'null' }] : []),
  ];

  const handleModeChange = (newMode: string) => {
    if (newMode === 'null') {
      setMode('null');
      onChange(null);
    } else {
      const idx = parseInt(newMode.replace('type_', ''), 10);
      setMode(idx);
      onChange('');
    }
  };

  const currentSegmentedValue = isNullMode ? 'null' : `type_${mode}`;

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
      {/* Type selector */}
      <SegmentedControl
        value={currentSegmentedValue}
        onChange={handleModeChange}
        data={segmentedData}
        size="xs"
        fullWidth
        mb="xs"
      />
      {isNullMode ? (
        <Text size="xs" c="dimmed" fs="italic">Value will be null</Text>
      ) : (
        <PrimitiveValueInput
          key={`union-value-${mode}`}
          value={value}
          onChange={onChange}
          schema={schema!}
          defs={defs}
        />
      )}
    </Box>
  );
}

// ─── Connection field ──────────────────────────────────────────────────────

function ConnectionField({
  label,
  description,
  value,
  onChange,
  isRequired,
  infoIcon,
  property,
  defs,
  connections,
}: {
  label: string;
  description?: string;
  value: unknown;
  onChange: (v: unknown) => void;
  isRequired: boolean;
  infoIcon: React.ReactNode;
  property: JsonSchemaProperty;
  defs: Record<string, JsonSchemaProperty>;
  connections: Connection[];
}) {
  const allOf = (property as any).allOf;
  let connectionClassName: string | undefined;
  let connectionType: string | undefined;

  if (Array.isArray(allOf)) {
    const refItem = allOf.find((item: any) => item.$ref);
    if (refItem) {
      const refPath = refItem.$ref;
      const typeName = refPath.split('/').pop();
      connectionClassName = typeName;
      const def = defs[typeName];
      if (def && (def as any)['x-connection-type']) {
        connectionType = (def as any)['x-connection-type'];
      }
    }
  }

  const filteredConnections = connectionType
    ? connections.filter((c) => c.connection_type === connectionType)
    : connections;

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

// ─── FormField (main dispatcher) ───────────────────────────────────────────

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
  const fieldType = getFieldType(property, propertyName, defs);
  const schema = (resolveRef(property as Record<string, unknown>, defs) || property) as Record<string, unknown>;

  const label = propertyName;
  const description = property.description;
  const typeLabel = getTypeLabel(schema, defs);

  const infoIcon = description ? (
    <Tooltip label={description} multiline withArrow w={200}>
      <IconInfoCircle size={14} style={{ marginLeft: 4, cursor: 'help', flexShrink: 0 }} />
    </Tooltip>
  ) : null;

  if (fieldType === 'connection') {
    return (
      <ConnectionField
        label={label} description={description} value={value} onChange={onChange}
        isRequired={isRequired} infoIcon={infoIcon} property={property} defs={defs} connections={connections}
      />
    );
  }

  if (fieldType === 'boolean') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
        </Group>
        <Select
          value={value === true ? 'true' : 'false'}
          onChange={(v) => onChange(v === 'true')}
          data={[
            { value: 'true', label: 'True' },
            { value: 'false', label: 'False' },
          ]}
          size="sm"
        />
      </Box>
    );
  }

  if (fieldType === 'optionalBoolean') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>{label}</Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
        </Group>
        <Select
          value={value === null || value === undefined ? 'null' : value ? 'true' : 'false'}
          onChange={(v) => {
            if (v === 'null') onChange(null);
            else onChange(v === 'true');
          }}
          data={[
            { value: 'true', label: 'True' },
            { value: 'false', label: 'False' },
            { value: 'null', label: 'Не указано' },
          ]}
          size="sm"
          clearable
        />
      </Box>
    );
  }

  if (fieldType === 'integer') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
        </Group>
        <NumberInput
          value={value !== undefined && value !== null ? Number(value) : undefined}
          onChange={(v) => onChange(v !== '' && v !== null && v !== undefined ? Number(v) : null)}
          step={1}
          allowDecimal={false}
          hideControls
          size="sm"
        />
      </Box>
    );
  }

  if (fieldType === 'number') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
        </Group>
        <NumberInput
          value={value !== undefined && value !== null ? Number(value) : undefined}
          onChange={(v) => onChange(v !== '' && v !== null && v !== undefined ? Number(v) : null)}
          step={0.1}
          hideControls
          size="sm"
        />
      </Box>
    );
  }

  if (fieldType === 'date') {
    const dateValue = value ? dayjs(value as string).toDate() : null;
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
        </Group>
        <DateInput
          value={dateValue}
          onChange={(d: Date | null) => {
            if (d) onChange(dayjs(d).format('YYYY-MM-DD'));
            else onChange(null);
          }}
          size="sm"
          valueFormat="YYYY-MM-DD"
          clearable
        />
      </Box>
    );
  }

  if (fieldType === 'datetime') {
    const dateValue = value ? dayjs(value as string).toDate() : null;
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
        </Group>
        <DateTimePicker
          value={dateValue}
          onChange={(d: Date | null) => {
            if (d) onChange(dayjs(d).utc().format());
            else onChange(null);
          }}
          size="sm"
          valueFormat="YYYY-MM-DD HH:mm:ss"
          clearable
        />
      </Box>
    );
  }

  if (fieldType === 'textarea') {
    return (
      <Box mb="md">
        <Group wrap="nowrap" mb={4} gap={4}>
          <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
            {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
          </Text>
          {infoIcon}
          <Badge size="xs" variant="light">{typeLabel}</Badge>
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

  if (fieldType === 'dict') {
    return (
      <DictField
        label={label} typeLabel={typeLabel} value={value} onChange={onChange}
        isRequired={isRequired} infoIcon={infoIcon}
        additionalProperties={schema.additionalProperties as Record<string, unknown>}
        defs={defs}
      />
    );
  }

  if (fieldType === 'list') {
    return (
      <ListField
        label={label} typeLabel={typeLabel} value={value} onChange={onChange}
        isRequired={isRequired} infoIcon={infoIcon}
        itemsSchema={schema.items as Record<string, unknown>}
        defs={defs}
      />
    );
  }

  if (fieldType === 'union') {
    return (
      <UnionField
        label={label} typeLabel={typeLabel} value={value} onChange={onChange}
        isRequired={isRequired} infoIcon={infoIcon}
        anyOf={schema.anyOf as Record<string, unknown>[]}
        defs={defs}
      />
    );
  }

  // Default text
  return (
    <Box mb="md">
      <Group wrap="nowrap" mb={4} gap={4}>
        <Text size="sm" fw={500} style={{ minWidth: 0, flex: 1 }}>
          {label}{isRequired && <Text span c="red" fw={700} ml={4}>*</Text>}
        </Text>
        {infoIcon}
        <Badge size="xs" variant="light">{typeLabel}</Badge>
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

// ─── NodeParamsForm (main export) ──────────────────────────────────────────

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
    if (!inputSchema?.properties) return {};
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
    <Box
      mt="md"
      style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
      }}
    >
      <Stack gap="xs" style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
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
    </Box>
  );
}
