"""Unit test suite for aws_encryption_sdk.streaming_client.StreamDecryptor"""
import io
import unittest

from mock import MagicMock, patch, sentinel, call
import six

from aws_encryption_sdk.exceptions import NotSupportedError, SerializationError
from aws_encryption_sdk.identifiers import ContentType
from aws_encryption_sdk.key_providers.base import MasterKeyProvider
from aws_encryption_sdk.streaming_client import StreamDecryptor
from .test_values import VALUES


class TestStreamDecryptor(unittest.TestCase):

    def setUp(self):
        self.mock_key_provider = MagicMock()
        self.mock_key_provider.__class__ = MasterKeyProvider
        self.mock_key_provider.decrypt_data_key_from_list.return_value = VALUES['data_key_obj']
        self.mock_header = MagicMock()
        self.mock_header.algorithm = sentinel.algorithm
        self.mock_header.encrypted_data_keys = sentinel.encrypted_data_keys
        self.mock_header.encryption_context = sentinel.encryption_context

        self.mock_input_stream = MagicMock()
        self.mock_input_stream.__class__ = io.IOBase
        self.mock_input_stream.tell.side_effect = (0, 500)

        # Set up deserialize_header patch
        self.mock_deserialize_header_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.deserialize_header'
        )
        self.mock_deserialize_header = self.mock_deserialize_header_patcher.start()
        self.mock_deserialize_header.return_value = self.mock_header
        # Set up verifier_from_header patch
        self.mock_verifier_from_header_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.verifier_from_header'
        )
        self.mock_verifier_from_header = self.mock_verifier_from_header_patcher.start()
        # Set up deserialize_header_auth patch
        self.mock_deserialize_header_auth_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.deserialize_header_auth'
        )
        self.mock_deserialize_header_auth = self.mock_deserialize_header_auth_patcher.start()
        self.mock_deserialize_header_auth.return_value = sentinel.header_auth
        # Set up validate_header patch
        self.mock_validate_header_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.validate_header'
        )
        self.mock_validate_header = self.mock_validate_header_patcher.start()
        # Set up deserialize_single_block_values patch
        self.mock_deserialize_single_block_values_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.deserialize_single_block_values'
        )
        self.mock_deserialize_single_block_values = self.mock_deserialize_single_block_values_patcher.start()
        self.mock_deserialize_single_block_values.return_value = (sentinel.iv, sentinel.tag, len(VALUES['data_128']))
        # Set up get_aad_content_string patch
        self.mock_get_aad_content_string_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.utils.get_aad_content_string'
        )
        self.mock_get_aad_content_string = self.mock_get_aad_content_string_patcher.start()
        self.mock_get_aad_content_string.return_value = sentinel.aad_content_string
        # Set up assemble_content_aad patch
        self.mock_assemble_content_aad_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.encryption_context.assemble_content_aad'
        )
        self.mock_assemble_content_aad = self.mock_assemble_content_aad_patcher.start()
        self.mock_assemble_content_aad.return_value = sentinel.associated_data
        # Set up Decryptor patch
        self.mock_decryptor_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.crypto.Decryptor'
        )
        self.mock_decryptor = self.mock_decryptor_patcher.start()
        self.mock_decryptor_instance = MagicMock()
        self.mock_decryptor.return_value = self.mock_decryptor_instance
        # Set up update_verifier_with_tag patch
        self.mock_update_verifier_with_tag_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.update_verifier_with_tag'
        )
        self.mock_update_verifier_with_tag = self.mock_update_verifier_with_tag_patcher.start()
        # Set up deserialize_footer patch
        self.mock_deserialize_footer_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.deserialize_footer'
        )
        self.mock_deserialize_footer = self.mock_deserialize_footer_patcher.start()
        # Set up deserialize_frame patch
        self.mock_deserialize_frame_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.formatting.deserialize.deserialize_frame'
        )
        self.mock_deserialize_frame = self.mock_deserialize_frame_patcher.start()
        # Set up decrypt patch
        self.mock_decrypt_patcher = patch(
            'aws_encryption_sdk.streaming_client.aws_encryption_sdk.internal.crypto.decrypt'
        )
        self.mock_decrypt = self.mock_decrypt_patcher.start()

    def tearDown(self):
        self.mock_deserialize_header_patcher.stop()
        self.mock_verifier_from_header_patcher.stop()
        self.mock_deserialize_header_auth_patcher.stop()
        self.mock_validate_header_patcher.stop()
        self.mock_deserialize_single_block_values_patcher.stop()
        self.mock_get_aad_content_string_patcher.stop()
        self.mock_assemble_content_aad_patcher.stop()
        self.mock_decryptor_patcher.stop()
        self.mock_update_verifier_with_tag_patcher.stop()
        self.mock_deserialize_footer_patcher.stop()
        self.mock_deserialize_frame_patcher.stop()
        self.mock_decrypt_patcher.stop()

    def test_init(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        assert test_decryptor.last_sequence_number == 0

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._prep_single_block')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_header')
    def test_prep_message_framed_message(self, mock_read_header, mock_prep_single_block):
        self.mock_header.content_type = ContentType.FRAMED_DATA
        mock_read_header.return_value = self.mock_header, sentinel.header_auth
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=self.mock_input_stream
        )
        test_decryptor._prep_message()
        mock_read_header.assert_called_once_with()
        assert test_decryptor.header is self.mock_header
        assert test_decryptor.header_auth is sentinel.header_auth
        assert not mock_prep_single_block.called
        assert test_decryptor._message_prepped

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._prep_single_block')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_header')
    def test_prep_message_single_block_message(self, mock_read_header, mock_prep_single_block):
        self.mock_header.content_type = ContentType.NO_FRAMING
        mock_read_header.return_value = self.mock_header, sentinel.header_auth
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=self.mock_input_stream
        )
        test_decryptor._prep_message()
        mock_prep_single_block.assert_called_once_with()

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor.__init__')
    def test_read_header(self, mock_init):
        mock_verifier = MagicMock()
        self.mock_verifier_from_header.return_value = mock_verifier
        mock_init.return_value = None
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.key_provider = self.mock_key_provider
        test_decryptor.source_stream = ct_stream
        test_decryptor._stream_length = len(VALUES['data_128'])
        test_header, test_header_auth = test_decryptor._read_header()
        self.mock_deserialize_header.assert_called_once_with(ct_stream)
        self.mock_verifier_from_header.assert_called_once_with(self.mock_header)
        mock_verifier.update.assert_called_once_with(b'')
        self.mock_deserialize_header_auth.assert_called_once_with(
            stream=ct_stream,
            algorithm=sentinel.algorithm,
            verifier=mock_verifier
        )
        self.mock_key_provider.decrypt_data_key_from_list.assert_called_once_with(
            encrypted_data_keys=sentinel.encrypted_data_keys,
            algorithm=sentinel.algorithm,
            encryption_context=sentinel.encryption_context
        )
        self.mock_validate_header.assert_called_once_with(
            header=self.mock_header,
            header_auth=sentinel.header_auth,
            stream=ct_stream,
            header_start=0,
            header_end=0,  # Because we mock out deserialize_header, this stays at the start of the stream
            data_key=VALUES['data_key_obj']
        )
        assert test_header is self.mock_header
        assert test_header_auth is sentinel.header_auth

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor.__init__')
    def test_read_header_no_verifier(self, mock_init):
        self.mock_verifier_from_header.return_value = None
        mock_init.return_value = None
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=self.mock_input_stream
        )
        test_decryptor.key_provider = self.mock_key_provider
        test_decryptor.source_stream = self.mock_input_stream
        test_decryptor._stream_length = len(VALUES['data_128'])
        test_decryptor._read_header()

    def test_prep_single_block(self):
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=self.mock_input_stream
        )
        test_decryptor.header = self.mock_header
        test_decryptor.verifier = sentinel.verifier
        mock_data_key = MagicMock()
        test_decryptor.data_key = mock_data_key

        test_decryptor._prep_single_block()

        self.mock_deserialize_single_block_values.assert_called_once_with(
            stream=self.mock_input_stream,
            header=self.mock_header,
            verifier=sentinel.verifier
        )
        assert test_decryptor.body_length == len(VALUES['data_128'])
        self.mock_get_aad_content_string.assert_called_once_with(
            content_type=self.mock_header.content_type,
            is_final_frame=True
        )
        self.mock_assemble_content_aad.assert_called_once_with(
            message_id=self.mock_header.message_id,
            aad_content_string=sentinel.aad_content_string,
            seq_num=1,
            length=len(VALUES['data_128'])
        )
        self.mock_decryptor.assert_called_once_with(
            algorithm=self.mock_header.algorithm,
            key=mock_data_key.data_key,
            associated_data=sentinel.associated_data,
            message_id=self.mock_header.message_id,
            iv=sentinel.iv,
            tag=sentinel.tag
        )
        assert test_decryptor.decryptor is self.mock_decryptor_instance
        assert test_decryptor.body_start == 0
        assert test_decryptor.body_end == len(VALUES['data_128'])

    def test_read_bytes_from_single_block(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.body_start = 0
        test_decryptor.body_end = len(VALUES['data_128'])
        test_decryptor.decryptor = self.mock_decryptor_instance
        test_decryptor.verifier = MagicMock()
        self.mock_decryptor_instance.update.return_value = b'1234'
        test = test_decryptor._read_bytes_from_single_block_body(5)
        test_decryptor.verifier.update.assert_called_once_with(VALUES['data_128'][:5])
        self.mock_decryptor_instance.update.assert_called_once_with(VALUES['data_128'][:5])
        assert not test_decryptor.source_stream.closed
        assert test == b'1234'

    def test_read_bytes_from_single_block_no_verifier(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.body_start = 0
        test_decryptor.body_end = len(VALUES['data_128'])
        test_decryptor.decryptor = self.mock_decryptor_instance
        test_decryptor.verifier = None
        self.mock_decryptor_instance.update.return_value = b'1234'
        test_decryptor._read_bytes_from_single_block_body(5)

    def test_read_bytes_from_single_block_finalize(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.body_start = 0
        test_decryptor.body_end = len(VALUES['data_128'])
        test_decryptor.decryptor = self.mock_decryptor_instance
        test_decryptor.verifier = MagicMock()
        test_decryptor.header = self.mock_header
        self.mock_decryptor_instance.update.return_value = b'1234'
        self.mock_decryptor_instance.finalize.return_value = b'5678'
        test = test_decryptor._read_bytes_from_single_block_body(len(VALUES['data_128']) + 1)
        test_decryptor.verifier.update.assert_called_once_with(VALUES['data_128'])
        self.mock_decryptor_instance.update.assert_called_once_with(VALUES['data_128'])
        self.mock_update_verifier_with_tag.assert_called_once_with(
            stream=test_decryptor.source_stream,
            header=test_decryptor.header,
            verifier=test_decryptor.verifier
        )
        self.mock_deserialize_footer.assert_called_once_with(
            stream=test_decryptor.source_stream,
            verifier=test_decryptor.verifier
        )
        assert test_decryptor.source_stream.closed
        assert test == b'12345678'

    def test_read_bytes_from_framed_body_multi_frame_finalize(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.verifier = MagicMock()
        test_decryptor.data_key = MagicMock()
        test_decryptor.header = self.mock_header
        frame_data_1 = MagicMock()
        frame_data_1.sequence_number = 1
        frame_data_1.final_frame = False
        frame_data_1.ciphertext = b'qwer'
        frame_data_2 = MagicMock()
        frame_data_2.sequence_number = 2
        frame_data_2.final_frame = False
        frame_data_2.ciphertext = b'asdfg'
        frame_data_3 = MagicMock()
        frame_data_3.sequence_number = 3
        frame_data_3.final_frame = False
        frame_data_3.ciphertext = b'zxcvbn'
        frame_data_4 = MagicMock()
        frame_data_4.sequence_number = 4
        frame_data_4.final_frame = True
        frame_data_4.ciphertext = b'yuiohjk'
        self.mock_deserialize_frame.side_effect = (
            (frame_data_1, False),
            (frame_data_2, False),
            (frame_data_3, False),
            (frame_data_4, True)
        )
        self.mock_get_aad_content_string.side_effect = (
            sentinel.aad_content_string_1,
            sentinel.aad_content_string_2,
            sentinel.aad_content_string_3,
            sentinel.aad_content_string_4
        )
        self.mock_assemble_content_aad.side_effect = (
            sentinel.associated_data_1,
            sentinel.associated_data_2,
            sentinel.associated_data_3,
            sentinel.associated_data_4
        )
        self.mock_decrypt.side_effect = (
            b'123',
            b'456',
            b'789',
            b'0-='
        )
        test = test_decryptor._read_bytes_from_framed_body(12)
        self.mock_deserialize_frame.assert_has_calls(
            calls=(
                call(
                    stream=test_decryptor.source_stream,
                    header=test_decryptor.header,
                    verifier=test_decryptor.verifier
                ),
                call(
                    stream=test_decryptor.source_stream,
                    header=test_decryptor.header,
                    verifier=test_decryptor.verifier
                ),
                call(
                    stream=test_decryptor.source_stream,
                    header=test_decryptor.header,
                    verifier=test_decryptor.verifier
                ),
                call(
                    stream=test_decryptor.source_stream,
                    header=test_decryptor.header,
                    verifier=test_decryptor.verifier
                )
            ),
            any_order=False
        )
        self.mock_get_aad_content_string.assert_has_calls(
            calls=(
                call(content_type=test_decryptor.header.content_type, is_final_frame=False),
                call(content_type=test_decryptor.header.content_type, is_final_frame=False),
                call(content_type=test_decryptor.header.content_type, is_final_frame=False),
                call(content_type=test_decryptor.header.content_type, is_final_frame=True)
            ),
            any_order=False
        )
        self.mock_assemble_content_aad.assert_has_calls(
            calls=(
                call(
                    message_id=test_decryptor.header.message_id,
                    aad_content_string=sentinel.aad_content_string_1,
                    seq_num=1,
                    length=4
                ),
                call(
                    message_id=test_decryptor.header.message_id,
                    aad_content_string=sentinel.aad_content_string_2,
                    seq_num=2,
                    length=5
                ),
                call(
                    message_id=test_decryptor.header.message_id,
                    aad_content_string=sentinel.aad_content_string_3,
                    seq_num=3,
                    length=6
                ),
                call(
                    message_id=test_decryptor.header.message_id,
                    aad_content_string=sentinel.aad_content_string_4,
                    seq_num=4,
                    length=7
                )
            ),
            any_order=False
        )
        self.mock_decrypt.assert_has_calls(
            calls=(
                call(
                    algorithm=test_decryptor.header.algorithm,
                    key=test_decryptor.data_key.data_key,
                    encrypted_data=frame_data_1,
                    associated_data=sentinel.associated_data_1,
                    message_id=test_decryptor.header.message_id
                ),
                call(
                    algorithm=test_decryptor.header.algorithm,
                    key=test_decryptor.data_key.data_key,
                    encrypted_data=frame_data_2,
                    associated_data=sentinel.associated_data_2,
                    message_id=test_decryptor.header.message_id
                ),
                call(
                    algorithm=test_decryptor.header.algorithm,
                    key=test_decryptor.data_key.data_key,
                    encrypted_data=frame_data_3,
                    associated_data=sentinel.associated_data_3,
                    message_id=test_decryptor.header.message_id
                ),
                call(
                    algorithm=test_decryptor.header.algorithm,
                    key=test_decryptor.data_key.data_key,
                    encrypted_data=frame_data_4,
                    associated_data=sentinel.associated_data_4,
                    message_id=test_decryptor.header.message_id
                )
            ),
            any_order=False
        )
        self.mock_deserialize_footer.assert_called_once_with(
            stream=test_decryptor.source_stream,
            verifier=test_decryptor.verifier
        )
        assert test_decryptor.source_stream.closed
        assert test == b'1234567890-='

    def test_read_bytes_from_framed_body_single_frame(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.verifier = MagicMock()
        test_decryptor.data_key = MagicMock()
        test_decryptor.header = self.mock_header
        frame_data = MagicMock()
        frame_data.sequence_number = 1
        frame_data.final_frame = False
        frame_data.ciphertext = b'asdfzxcv'
        self.mock_deserialize_frame.return_value = (frame_data, False)
        self.mock_get_aad_content_string.return_value = sentinel.aad_content_string
        self.mock_assemble_content_aad.return_value = sentinel.associated_data
        self.mock_decrypt.return_value = b'1234'
        test = test_decryptor._read_bytes_from_framed_body(4)
        self.mock_deserialize_frame.assert_called_once_with(
            stream=test_decryptor.source_stream,
            header=test_decryptor.header,
            verifier=test_decryptor.verifier
        )
        assert not self.mock_deserialize_footer.called
        assert not test_decryptor.source_stream.closed
        assert test == b'1234'

    def test_read_bytes_from_framed_body_bad_sequence_number(self):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.verifier = MagicMock()
        test_decryptor.header = self.mock_header
        frame_data = MagicMock()
        frame_data.sequence_number = 5
        frame_data.final_frame = False
        frame_data.ciphertext = b'asdfzxcv'
        self.mock_deserialize_frame.return_value = (frame_data, False)
        with six.assertRaisesRegex(self, SerializationError, 'Malformed message: frames out of order'):
            test_decryptor._read_bytes_from_framed_body(4)

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_single_block_body')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_framed_body')
    def test_read_bytes_closed(self, mock_read_frame, mock_read_block):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.source_stream.close()
        test_decryptor._read_bytes(5)
        assert not mock_read_frame.called
        assert not mock_read_block.called

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_single_block_body')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_framed_body')
    def test_read_bytes_no_read_required(self, mock_read_frame, mock_read_block):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.output_buffer = b'1234567'
        test_decryptor._read_bytes(5)
        assert not mock_read_frame.called
        assert not mock_read_block.called

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_single_block_body')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_framed_body')
    def test_read_bytes_framed(self, mock_read_frame, mock_read_block):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.header = MagicMock()
        test_decryptor.header.content_type = ContentType.FRAMED_DATA
        test_decryptor._read_bytes(5)
        mock_read_frame.assert_called_once_with(5)
        assert not mock_read_block.called

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_single_block_body')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_framed_body')
    def test_read_bytes_single_block(self, mock_read_frame, mock_read_block):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.header = MagicMock()
        test_decryptor.header.content_type = ContentType.NO_FRAMING
        test_decryptor._read_bytes(5)
        mock_read_block.assert_called_once_with(5)
        assert not mock_read_frame.called

    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_single_block_body')
    @patch('aws_encryption_sdk.streaming_client.StreamDecryptor._read_bytes_from_framed_body')
    def test_read_bytes_unknown(self, mock_read_frame, mock_read_block):
        ct_stream = io.BytesIO(VALUES['data_128'])
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=ct_stream
        )
        test_decryptor.header = MagicMock()
        test_decryptor.header.content_type = None
        with six.assertRaisesRegex(self, NotSupportedError, 'Unsupported content type'):
            test_decryptor._read_bytes(5)

    @patch('aws_encryption_sdk.streaming_client._EncryptionStream.close')
    def test_close(self, mock_close):
        self.mock_header.content_type = ContentType.NO_FRAMING
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=self.mock_input_stream
        )
        test_decryptor.footer = sentinel.footer
        test_decryptor.data_key = VALUES['data_key_obj']
        test_decryptor.close()
        mock_close.assert_called_once_with()

    @patch('aws_encryption_sdk.streaming_client._EncryptionStream.close')
    def test_close_no_footer(self, mock_close):
        self.mock_header.content_type = ContentType.FRAMED_DATA
        test_decryptor = StreamDecryptor(
            key_provider=self.mock_key_provider,
            source=self.mock_input_stream
        )
        with six.assertRaisesRegex(self, SerializationError, 'Footer not read'):
            test_decryptor.close()
