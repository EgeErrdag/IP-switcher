import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


class NormalizeIPv4Test(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(main.normalize_ipv4("192.168.001.010"), "192.168.1.10")
        self.assertEqual(main.normalize_ipv4(" 10.0.0.1\n"), "10.0.0.1")

    def test_invalid(self):
        for text in ("", None, "1.2.3", "1.2.3.256", "a.b.c.d", "1.2.3.4.5"):
            self.assertIsNone(main.normalize_ipv4(text), text)


class ValidateStaticConfigTest(unittest.TestCase):
    def test_ok(self):
        self.assertIsNone(main.validate_static_config("192.168.1.10", "255.255.255.0", "192.168.1.1",
                                                      ("8.8.8.8", "1.1.1.1")))
        self.assertIsNone(main.validate_static_config("10.0.0.5", "255.0.0.0"))

    def test_bad_mask(self):
        self.assertIn("subnet mask", main.validate_static_config("10.0.0.5", "255.0.255.0"))
        self.assertIsNotNone(main.validate_static_config("10.0.0.5", "0.0.0.0"))

    def test_network_and_broadcast(self):
        self.assertIsNotNone(main.validate_static_config("192.168.1.0", "255.255.255.0"))
        self.assertIsNotNone(main.validate_static_config("192.168.1.255", "255.255.255.0"))

    def test_gateway(self):
        self.assertIn("outside", main.validate_static_config("192.168.1.10", "255.255.255.0", "192.168.2.1"))
        self.assertIsNotNone(main.validate_static_config("192.168.1.10", "255.255.255.0", "192.168.1.10"))

    def test_unassignable(self):
        for ip in ("127.0.0.1", "224.0.0.5", "0.0.0.0", "255.255.255.255"):
            self.assertIsNotNone(main.validate_static_config(ip, "255.255.255.0"), ip)


class CommandBuilderTest(unittest.TestCase):
    def test_static_two_dns(self):
        cmds = main.build_static_commands("Ethernet 2", "10.0.0.5", "255.255.255.0", "10.0.0.1",
                                          "8.8.8.8", "1.1.1.1")
        self.assertEqual(cmds[0][5], "name=Ethernet 2")
        self.assertIn("gateway=10.0.0.1", cmds[0])
        self.assertIn("address=8.8.8.8", cmds[1])
        self.assertEqual(cmds[2][3], "add")
        self.assertIn("index=2", cmds[2])

    def test_static_no_gateway_no_dns(self):
        cmds = main.build_static_commands("Wi-Fi", "10.0.0.5", "255.255.255.0")
        self.assertIn("gateway=none", cmds[0])
        self.assertEqual(len(cmds), 2)
        self.assertIn("address=none", cmds[1])

    def test_alt_dns_only_becomes_primary(self):
        cmds = main.build_static_commands("Wi-Fi", "10.0.0.5", "255.255.255.0", dns2="1.1.1.1")
        self.assertIn("address=1.1.1.1", cmds[1])
        self.assertEqual(len(cmds), 2)

    def test_dhcp(self):
        cmds = main.build_dhcp_commands("Wi-Fi")
        self.assertTrue(all("source=dhcp" in c for c in cmds))


class ProfileFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "saved_ips.json")

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file(self):
        self.assertEqual(main.load_profiles(self.path), ([], None))

    def test_round_trip(self):
        profiles = [{"name": "Ofis Ağı", "ip": "10.0.0.5", "subnet": "255.255.255.0"}]
        main.save_profiles(self.path, profiles)
        self.assertEqual(main.load_profiles(self.path), (profiles, None))

    def test_corrupt_file_is_moved_aside_not_lost(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        profiles, warning = main.load_profiles(self.path)
        self.assertEqual(profiles, [])
        self.assertIsNotNone(warning)
        backups = [n for n in os.listdir(self.dir.name) if n.startswith("saved_ips.json.broken-")]
        self.assertEqual(len(backups), 1)
        self.assertFalse(os.path.exists(self.path))

    def test_legacy_profile_kept(self):
        with open(self.path, "w") as f:
            json.dump([{"name": "Old", "ip": "192.168.1.5"}, "junk"], f)
        profiles, _ = main.load_profiles(self.path)
        self.assertEqual(profiles, [{"name": "Old", "ip": "192.168.1.5"}])


if __name__ == "__main__":
    unittest.main()
