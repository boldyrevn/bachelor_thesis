import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
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
  IconPlayerPlay,
} from '@tabler/icons-react';
import { ConnectionsPage } from './components/ConnectionsPage';
import { PipelinesPage } from './components/PipelineListPage';
import { PipelineRunsPage } from './components/PipelineRunsPage';
import { PipelineEditor } from './flows/PipelineEditor';
import { PipelineRunPage } from './flows/PipelineRunPage';
import { HeaderActionsProvider, useHeaderActions } from './context/HeaderActionsContext';
import { PipelineNameProvider, usePipelineName } from './context/PipelineNameContext';
import { getPipeline } from './api/pipelines';

/**
 * Static breadcrumb map for simple routes
 * Dynamic routes (e.g. /pipelines/:id/update) use DynamicBreadcrumbs component
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
  '/runs': [
    { label: 'Home', href: '/' },
    { label: 'Runs' },
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
        <NavItem
          to="/runs"
          icon={<IconPlayerPlay size={ICON_SIZE} />}
          label="Runs"
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

/**
 * Dynamic breadcrumbs component that fetches pipeline names for dynamic routes
 */
function DynamicBreadcrumbs() {
  const location = useLocation();
  const { pipelineName, setPipelineName } = usePipelineName();

  const path = location.pathname;
  const isUpdateRoute = /^\/pipelines\/[^/]+\/update$/.test(path);
  const isRunRoute = /^\/pipelines\/[^/]+\/runs\/[^/]+$/.test(path);
  const isDynamicRoute = isUpdateRoute || isRunRoute;

  // Extract pipelineId and runId from pathname directly (useParams doesn't work outside <Routes>)
  const pipelineIdMatch = path.match(/^\/pipelines\/([^/]+)/);
  const pipelineId = pipelineIdMatch ? pipelineIdMatch[1] : null;
  const runIdMatch = path.match(/^\/pipelines\/[^/]+\/runs\/([^/]+)$/);
  const runId = runIdMatch ? runIdMatch[1] : null;

  // Fetch pipeline name when on dynamic route
  useEffect(() => {
    if (!isDynamicRoute || !pipelineId) {
      setPipelineName(null);
      return;
    }

    getPipeline(pipelineId)
      .then((p) => {
        setPipelineName(p.name);
      })
      .catch((err) => {
        console.error('[DynamicBreadcrumbs] Failed to fetch pipeline:', err);
        setPipelineName('Unknown');
      });
  }, [pipelineId]);

  // Check if we're on a static route first
  const staticBreadcrumbs = BREADCRUMB_MAP[path];
  if (staticBreadcrumbs) {
    return (
      <Breadcrumbs separator={<IconChevronRight size={14} />} ml="xl" style={{ flex: 1 }}>
        {staticBreadcrumbs.map((crumb, index) =>
          crumb.href ? (
            <Anchor key={index} component={Link} to={crumb.href} underline="never" c="dimmed">
              {crumb.label}
            </Anchor>
          ) : (
            <Text key={index} c="dimmed" size="sm">
              {crumb.label}
            </Text>
          )
        )}
      </Breadcrumbs>
    );
  }

  // Dynamic route: /pipelines/:pipelineId/update
  if (isUpdateRoute) {
    return (
      <Breadcrumbs separator={<IconChevronRight size={14} />} ml="xl" style={{ flex: 1 }}>
        <Anchor component={Link} to="/" underline="never" c="dimmed">
          Home
        </Anchor>
        <Anchor component={Link} to="/pipelines" underline="never" c="dimmed">
          Pipelines
        </Anchor>
        <Text c="dimmed" size="sm">
          {pipelineName || 'Loading...'}
        </Text>
        <Text c="dimmed" size="sm">
          Update
        </Text>
      </Breadcrumbs>
    );
  }

  // Dynamic route: /pipelines/:pipelineId/runs/:runId
  if (isRunRoute) {
    return (
      <Breadcrumbs separator={<IconChevronRight size={14} />} ml="xl" style={{ flex: 1 }}>
        <Anchor component={Link} to="/" underline="never" c="dimmed">
          Home
        </Anchor>
        <Anchor component={Link} to="/pipelines" underline="never" c="dimmed">
          Pipelines
        </Anchor>
        {pipelineName ? (
          <Anchor component={Link} to={`/pipelines/${pipelineId}/update`} underline="never" c="dimmed">
            {pipelineName}
          </Anchor>
        ) : (
          <Text c="dimmed" size="sm">
            Loading...
          </Text>
        )}
        <Text c="dimmed" size="sm">
          Run {runId?.slice(0, 8)}...
        </Text>
      </Breadcrumbs>
    );
  }

  // Fallback
  return (
    <Breadcrumbs separator={<IconChevronRight size={14} />} ml="xl" style={{ flex: 1 }}>
      <Anchor component={Link} to="/" underline="never" c="dimmed">
        Home
      </Anchor>
    </Breadcrumbs>
  );
}

function AppContent() {
  const location = useLocation();
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(false);
  const [navbarCollapsed, { toggle: toggleNavbar }] = useDisclosure(false);

  const navbarWidth = navbarCollapsed ? NAVBAR_WIDTH_COLLAPSED : NAVBAR_WIDTH_EXPANDED;
  const isEditor = location.pathname === '/pipelines/new'
    || !!location.pathname.match(/^\/pipelines\/[^/]+\/update$/)
    || !!location.pathname.match(/^\/pipelines\/[^/]+\/runs\/[^/]+$/);

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
          <DynamicBreadcrumbs />
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
          <Route
            path="/runs"
            element={
              <PageWrapper>
                <PipelineRunsPage />
              </PageWrapper>
            }
          />
          <Route path="/pipelines/new" element={<PipelineEditor />} />
          <Route path="/pipelines/:pipelineId/update" element={<PipelineEditor />} />
          <Route path="/pipelines/:pipelineId/runs/:runId" element={<PipelineRunPage />} />
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
        <PipelineNameProvider>
          <AppContent />
        </PipelineNameProvider>
      </HeaderActionsProvider>
    </BrowserRouter>
  );
}

export default App;
