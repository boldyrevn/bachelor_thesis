import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  AppShell,
  Burger,
  Group,
  Text,
  Title,
  ActionIcon,
  Breadcrumbs,
  Anchor,
  Box,
  Tooltip,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconDatabase,
  IconHome,
  IconGitBranch,
  IconChevronRight,
  IconChevronsLeft,
  IconChevronsRight,
} from '@tabler/icons-react';
import { ConnectionsPage } from './components/ConnectionsPage';
import { PipelinesPage } from './components/PipelineListPage';
import { PipelineEditor } from './flows/PipelineEditor';
import { HeaderActionsProvider, useHeaderActions } from './context/HeaderActionsContext';

/**
 * Breadcrumb items for each route
 */
const BREADCRUMB_MAP: Record<string, { label: string; href?: string }[]> = {
  '/': [{ label: 'Home', href: '/' }],
  '/connections': [
    { label: 'Home', href: '/' },
    { label: 'Connections' },
  ],
  '/pipelines': [
    { label: 'Home', href: '/' },
    { label: 'Pipelines' },
  ],
  '/pipelines/new': [
    { label: 'Home', href: '/' },
    { label: 'Pipelines', href: '/pipelines' },
    { label: 'New Pipeline' },
  ],
};

const NAV_ITEM_HEIGHT = 44;
const ICON_SIZE = 20;
const NAVBAR_WIDTH_COLLAPSED = 60;
const NAVBAR_WIDTH_EXPANDED = 250;
// Icon position: centered in collapsed navbar
// (60 - 20) / 2 = 20px from left edge
const ICON_LEFT_OFFSET = 20;

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  collapsed: boolean;
}

function NavItem({ to, icon, label, collapsed }: NavItemProps) {
  const location = useLocation();
  const isActive = location.pathname === to;

  const content = (
    <Link
      to={to}
      style={{
        display: 'flex',
        alignItems: 'center',
        height: NAV_ITEM_HEIGHT,
        width: '100%',
        paddingLeft: ICON_LEFT_OFFSET,
        paddingRight: 12,
        borderRadius: 8,
        backgroundColor: isActive ? '#e7f5ff' : 'transparent',
        color: isActive ? '#1971c2' : '#495057',
        textDecoration: 'none',
        transition: 'background-color 0.15s ease',
        boxSizing: 'border-box',
        gap: 12,
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          (e.currentTarget as HTMLElement).style.backgroundColor = '#f1f3f5';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent';
        }
      }}
    >
      <Box
        style={{
          width: ICON_SIZE,
          height: ICON_SIZE,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      {!collapsed && (
        <Text
          size="sm"
          fw={500}
          style={{
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            opacity: 1,
            transition: 'opacity 0.2s ease',
          }}
        >
          {label}
        </Text>
      )}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip label={label} position="right" withArrow>
        {content}
      </Tooltip>
    );
  }

  return content;
}

function Navigation({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      <nav
        style={{
          flex: 1,
          paddingTop: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <NavItem
          to="/"
          icon={<IconHome size={ICON_SIZE} />}
          label="Home"
          collapsed={collapsed}
        />
        <NavItem
          to="/connections"
          icon={<IconDatabase size={ICON_SIZE} />}
          label="Connections"
          collapsed={collapsed}
        />
        <NavItem
          to="/pipelines"
          icon={<IconGitBranch size={ICON_SIZE} />}
          label="Pipelines"
          collapsed={collapsed}
        />
      </nav>

      {/* Collapse toggle button — fixed width container for centering, full width border */}
      <Box
        style={{
          borderTop: '1px solid #dee2e6',
        }}
      >
        <Box
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 48,
            width: NAVBAR_WIDTH_COLLAPSED,
            boxSizing: 'border-box',
          }}
        >
          <ActionIcon
            variant="subtle"
            onClick={onToggle}
            p={0}
            style={{ width: ICON_SIZE, height: ICON_SIZE }}
          >
            {collapsed ? (
              <IconChevronsRight size={ICON_SIZE} />
            ) : (
              <IconChevronsLeft size={ICON_SIZE} />
            )}
          </ActionIcon>
        </Box>
      </Box>
    </Box>
  );
}

function HomePage() {
  return (
    <Group p="xl">
      <Text>Welcome to FlowForge</Text>
    </Group>
  );
}

function PageWrapper({ children }: { children: React.ReactNode }) {
  return <Box p="md">{children}</Box>;
}

function AppContent() {
  const location = useLocation();
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(false);
  const [navbarCollapsed, { toggle: toggleNavbar }] = useDisclosure(false);

  // Build breadcrumbs from current path
  const breadcrumbs = BREADCRUMB_MAP[location.pathname] || [
    { label: 'Home', href: '/' },
  ];

  const navbarWidth = navbarCollapsed ? NAVBAR_WIDTH_COLLAPSED : NAVBAR_WIDTH_EXPANDED;
  const isEditor = location.pathname === '/pipelines/new';

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: navbarWidth,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened, desktop: !desktopOpened },
      }}
      padding={isEditor ? 0 : 'md'}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
            />
            <Burger
              onClick={toggleDesktop}
              visibleFrom="sm"
              size="sm"
            />
            <Title order={3}>FlowForge</Title>
          </Group>

          {/* Breadcrumbs */}
          <Breadcrumbs
            separator={<IconChevronRight size={14} />}
            ml="xl"
            style={{ flex: 1 }}
          >
            {breadcrumbs.map((crumb, index) =>
              crumb.href ? (
                <Anchor
                  key={index}
                  component={Link}
                  to={crumb.href}
                  underline="never"
                  c="dimmed"
                >
                  {crumb.label}
                </Anchor>
              ) : (
                <Text key={index} c="dimmed" size="sm">
                  {crumb.label}
                </Text>
              )
            )}
          </Breadcrumbs>
          <HeaderActionsSlot />
        </Group>
      </AppShell.Header>

      <AppShell.Navbar style={{ padding: 0 }}>
        <Navigation collapsed={navbarCollapsed} onToggle={toggleNavbar} />
      </AppShell.Navbar>

      <AppShell.Main style={{ height: 'calc(100vh - 60px)' }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route
            path="/connections"
            element={
              <PageWrapper>
                <ConnectionsPage />
              </PageWrapper>
            }
          />
          <Route
            path="/pipelines"
            element={
              <PageWrapper>
                <PipelinesPage />
              </PageWrapper>
            }
          />
          <Route path="/pipelines/new" element={<PipelineEditor />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}

/**
 * Renders header action buttons registered by child pages
 */
function HeaderActionsSlot() {
  const { actions } = useHeaderActions();
  return <Group>{actions}</Group>;
}

function App() {
  return (
    <BrowserRouter>
      <HeaderActionsProvider>
        <AppContent />
      </HeaderActionsProvider>
    </BrowserRouter>
  );
}

export default App;
