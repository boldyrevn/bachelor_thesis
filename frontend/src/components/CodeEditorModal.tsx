import { useState } from 'react';
import { Modal, Select, Group, Text, Stack } from '@mantine/core';
import Editor from 'react-simple-code-editor';
import Prism from 'prismjs';

// Load Prism language grammars
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-json';
import 'prismjs/themes/prism.css';

export type Language = 'sql' | 'python' | 'json' | 'plain';

interface CodeEditorModalProps {
  opened: boolean;
  onClose: () => void;
  value: string;
  onChange: (value: string) => void;
  label: string;
  description?: string;
  defaultLanguage?: Language;
}

const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
  { value: 'sql', label: 'SQL' },
  { value: 'python', label: 'Python' },
  { value: 'json', label: 'JSON' },
  { value: 'plain', label: 'Plain Text' },
];

const HIGHLIGHTERS: Record<Language, (code: string) => string> = {
  sql: (code: string) => Prism.highlight(code, Prism.languages.sql, 'sql'),
  python: (code: string) => Prism.highlight(code, Prism.languages.python, 'python'),
  json: (code: string) => Prism.highlight(code, Prism.languages.json, 'json'),
  plain: (code: string) => code,
};

export function CodeEditorModal({
  opened,
  onClose,
  value,
  onChange,
  label,
  description,
  defaultLanguage = 'sql',
}: CodeEditorModalProps) {
  const [language, setLanguage] = useState<Language>(defaultLanguage);

  const highlight = HIGHLIGHTERS[language];

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={label}
      size="90%"
      centered
      styles={{ body: { height: '80vh' } }}
    >
      <Stack h="100%">
        {description && <Text size="sm" c="dimmed">{description}</Text>}

        <Group justify="flex-end">
          <Select
            value={language}
            onChange={(v) => setLanguage((v as Language) || 'plain')}
            data={LANGUAGE_OPTIONS}
            size="xs"
            w={140}
            allowDeselect={false}
          />
        </Group>

        <div
          style={{
            flex: 1,
            border: '1px solid #dee2e6',
            borderRadius: 4,
            overflow: 'hidden',
          }}
        >
          <Editor
            value={value}
            onValueChange={onChange}
            highlight={highlight}
            padding={12}
            style={{
              fontFamily: '"Fira Code", "Cascadia Code", Menlo, monospace',
              fontSize: 14,
              lineHeight: 1.6,
              minHeight: '100%',
              backgroundColor: '#fafafa',
            }}
          />
        </div>
      </Stack>
    </Modal>
  );
}
