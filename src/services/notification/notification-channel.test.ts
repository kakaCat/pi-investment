import { describe, it, expect } from '@jest/globals';
import { NotificationChannel, NotificationMessage } from './notification-channel.js';

class TestChannel extends NotificationChannel {
  public lastMessage: NotificationMessage | null = null;
  public lastImage: { url: string; caption?: string } | null = null;
  public available = true;

  async send(message: NotificationMessage): Promise<void> {
    this.lastMessage = message;
  }

  async sendImage(imageUrl: string, caption?: string): Promise<void> {
    this.lastImage = { url: imageUrl, caption };
  }

  isAvailable(): boolean {
    return this.available;
  }
}

describe('NotificationChannel', () => {
  it('should allow concrete implementation to send message', async () => {
    const channel = new TestChannel();
    const message: NotificationMessage = {
      content: 'Test message',
      type: 'text'
    };

    await channel.send(message);

    expect(channel.lastMessage).toEqual(message);
  });

  it('should allow concrete implementation to send image', async () => {
    const channel = new TestChannel();

    await channel.sendImage('https://example.com/image.png', 'Test caption');

    expect(channel.lastImage).toEqual({
      url: 'https://example.com/image.png',
      caption: 'Test caption'
    });
  });

  it('should check availability', () => {
    const channel = new TestChannel();
    expect(channel.isAvailable()).toBe(true);

    channel.available = false;
    expect(channel.isAvailable()).toBe(false);
  });
});
