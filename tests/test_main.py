import unittest
from unittest import mock
import base64
import __main__ as main

class TestMain(unittest.TestCase):
    def setUp(self):
        self.ssh_key_data = "ssh-key-data"
        self.ssh_public_key = "ssh-public-key"
        self.user_data = main.USER_DATA
        self.user_data_base64 = base64.b64encode(self.user_data.encode("utf-8")).decode("utf-8")

    @mock.patch('builtins.open', new_callable=mock.mock_open, read_data="ssh-key-data")
    def test_read_ssh_keys(self, mock_open):
        with mock.patch('os.path.exists', return_value=True):
            ssh_key_data = main.read_ssh_key("ssh-key-path")
            self.assertEqual(ssh_key_data, self.ssh_key_data)

    def test_encode_user_data(self):
        encoded_user_data = main.encode_user_data(self.user_data)
        self.assertEqual(encoded_user_data, self.user_data_base64)

    @mock.patch('builtins.open', new_callable=mock.mock_open)
    def test_write_kubeconfig(self, mock_open):
        kubeconfig_data = "kubeconfig-data"
        main.write_kubeconfig(kubeconfig_data)
        mock_open.assert_called_once_with("out/rke_kubeconfig", "w", encoding="utf8")
        mock_open().write.assert_called_once_with(kubeconfig_data)

    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()
