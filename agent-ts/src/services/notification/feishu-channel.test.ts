import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { FeishuChannel } from './feishu-channel.js';
import { NotificationMessage } from './notification-channel.js';

describe('FeishuChannel', () => {
  let channel: FeishuChannel;
  let mockCreate: jest.Mock;

  beforeEach(() => {
    mockCreate = jest.fn<() => Promise<any>>().mockResolvedValue({ code: 0 });

    // Create channel and inject mock client
    channel = new FeishuChannel({
      appId: 'test-app-id',
      appSecret: 'test-app-secret',
      defaultChatId: 'test-chat-id'
    });

    // Replace the client's create method with our mock
    (channel as any).client = {
      im: {
        message: {
          create: mockCreate
        }
      }
    };
  });

  describe('isAvailable', () => {
    it('should return true when all config is present', () => {
      expect(channel.isAvailable()).toBe(true);
    });

    it('should return false when appId is missing', () => {
      const invalidChannel = new FeishuChannel({
        appId: '',
        appSecret: 'secret',
        defaultChatId: 'chat'
      });

      expect(invalidChannel.isAvailable()).toBe(false);
    });

    it('should return false when appSecret is missing', () => {
      const invalidChannel = new FeishuChannel({
        appId: 'app',
        appSecret: '',
        defaultChatId: 'chat'
      });

      expect(invalidChannel.isAvailable()).toBe(false);
    });

    it('should return false when defaultChatId is missing', () => {
      const invalidChannel = new FeishuChannel({
        appId: 'app',
        appSecret: 'secret',
        defaultChatId: ''
      });

      expect(invalidChannel.isAvailable()).toBe(false);
    });
  });

  describe('send', () => {
    it('should send text message', async () => {
      const message: NotificationMessage = {
        content: 'Test message',
        type: 'text'
      };

      await channel.send(message);

      expect(mockCreate).toHaveBeenCalledWith({
        params: { receive_id_type: 'chat_id' },
        data: {
          receive_id: 'test-chat-id',
          msg_type: 'text',
          content: JSON.stringify({ text: 'Test message' })
        }
      });
    });

    it('should send card message', async () => {
      const message: NotificationMessage = {
        title: 'Test Title',
        content: 'Test content',
        type: 'card'
      };

      await channel.send(message);

      expect(mockCreate).toHaveBeenCalledWith({
        params: { receive_id_type: 'chat_id' },
        data: {
          receive_id: 'test-chat-id',
          msg_type: 'interactive',
          content: expect.stringContaining('Test Title')
        }
      });

      const callArgs = mockCreate.mock.calls[0][0] as any;
      const card = JSON.parse(callArgs.data.content);
      expect(card.header.title.content).toBe('Test Title');
      expect(card.elements[0].content).toBe('Test content');
    });

    it('should split long messages', async () => {
      const longContent = 'a'.repeat(30000);
      const message: NotificationMessage = {
        content: longContent,
        type: 'card'
      };

      await channel.send(message);

      expect(mockCreate).toHaveBeenCalledTimes(2);
    });
  });

  describe('sendImage', () => {
    it('should send image with caption', async () => {
      await channel.sendImage('https://example.com/image.png', 'Test caption');

      expect(mockCreate).toHaveBeenCalledWith({
        params: { receive_id_type: 'chat_id' },
        data: {
          receive_id: 'test-chat-id',
          msg_type: 'interactive',
          content: expect.stringContaining('Test caption')
        }
      });
    });
  });
});
