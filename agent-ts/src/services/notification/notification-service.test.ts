import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { NotificationService, NotificationOptions } from './notification-service.js';
import { NotificationChannel, NotificationMessage } from './notification-channel.js';

class MockChannel extends NotificationChannel {
  public messages: NotificationMessage[] = [];
  public images: Array<{ url: string; caption?: string }> = [];
  public available = true;

  async send(message: NotificationMessage): Promise<void> {
    this.messages.push(message);
  }

  async sendImage(imageUrl: string, caption?: string): Promise<void> {
    this.images.push({ url: imageUrl, caption });
  }

  isAvailable(): boolean {
    return this.available;
  }
}

describe('NotificationService', () => {
  let service: NotificationService;
  let mockChannel: MockChannel;

  beforeEach(() => {
    mockChannel = new MockChannel();
    service = new NotificationService();
    service.registerChannel('test', mockChannel);
  });

  describe('send', () => {
    it('should send text message to default channel', async () => {
      await service.send('Hello world');

      expect(mockChannel.messages).toHaveLength(1);
      expect(mockChannel.messages[0]).toEqual({
        content: 'Hello world',
        type: 'text'
      });
    });

    it('should send message to specified channel', async () => {
      const anotherChannel = new MockChannel();
      service.registerChannel('another', anotherChannel);

      await service.send('Test', { channel: 'another' });

      expect(mockChannel.messages).toHaveLength(0);
      expect(anotherChannel.messages).toHaveLength(1);
    });

    it('should skip if channel is not available', async () => {
      mockChannel.available = false;
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

      await service.send('Test');

      expect(mockChannel.messages).toHaveLength(0);
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Channel test not available')
      );

      consoleSpy.mockRestore();
    });
  });

  describe('sendCard', () => {
    it('should send card message', async () => {
      const message: NotificationMessage = {
        title: 'Test Title',
        content: 'Test content',
        type: 'card',
        metadata: { key: 'value' }
      };

      await service.sendCard(message);

      expect(mockChannel.messages).toHaveLength(1);
      expect(mockChannel.messages[0]).toEqual(message);
    });
  });

  describe('sendImage', () => {
    it('should send image with caption', async () => {
      await service.sendImage('https://example.com/image.png', 'Test caption');

      expect(mockChannel.images).toHaveLength(1);
      expect(mockChannel.images[0]).toEqual({
        url: 'https://example.com/image.png',
        caption: 'Test caption'
      });
    });

    it('should send image without caption', async () => {
      await service.sendImage('https://example.com/image.png');

      expect(mockChannel.images).toHaveLength(1);
      expect(mockChannel.images[0]).toEqual({
        url: 'https://example.com/image.png',
        caption: undefined
      });
    });
  });

  describe('sendBatch', () => {
    it('should send multiple messages', async () => {
      const messages: NotificationMessage[] = [
        { content: 'Message 1', type: 'text' },
        { content: 'Message 2', type: 'text' },
        { content: 'Message 3', type: 'card', title: 'Title 3' }
      ];

      await service.sendBatch(messages);

      expect(mockChannel.messages).toHaveLength(3);
      expect(mockChannel.messages).toEqual(messages);
    });
  });
});
