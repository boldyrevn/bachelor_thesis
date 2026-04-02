import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  AppShell,
  Burger,
  Group,
  NavLink,
  Text,
  Title,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconDatabase, IconHome } from '@tabler/icons-react';
import { ConnectionsPage } from './components/ConnectionsPage';

function Navigation() {
  const location = useLocation();

  return (
    <nav>
      <NavLink
        component={Link}
        to="/"
        label="Home"
        leftSection={<IconHome size={16} />}
        active={location.pathname === '/'}
      />
      <NavLink
        component={Link}
        to="/connections"
        label="Connections"
        leftSection={<IconDatabase size={16} />}
        active={location.pathname === '/connections'}
      />
    </nav>
  );
}

function HomePage() {
  return (
    <Group p="xl">
      <Text>Welcome to FlowForge</Text>
    </Group>
  );
}

function AppContent() {
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: 250,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened, desktop: !desktopOpened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
            />
            <Burger
              opened={desktopOpened}
              onClick={toggleDesktop}
              visibleFrom="sm"
              size="sm"
            />
            <Title order={3}>FlowForge</Title>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Navigation />
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/connections" element={<ConnectionsPage />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
