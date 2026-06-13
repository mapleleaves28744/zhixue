import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { generateTTS } from '@/lib/audio/tts-providers';
import { transcribeAudio } from '@/lib/audio/asr-providers';

const mockFetch = vi.fn() as Mock;
vi.stubGlobal('fetch', mockFetch);

describe('Xiaomi MiMo audio providers', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('generates TTS through chat completions and decodes the returned audio', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        choices: [{ message: { audio: { data: Buffer.from('wav-audio').toString('base64') } } }],
      }),
    });

    const result = await generateTTS(
      {
        providerId: 'xiaomi-mimo-tts',
        apiKey: 'tp-test',
        baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1/',
        modelId: 'mimo-v2.5-tts',
        voice: 'mimo_default',
      },
      '你好',
    );

    expect(mockFetch).toHaveBeenCalledWith(
      'https://token-plan-cn.xiaomimimo.com/v1/chat/completions',
      expect.objectContaining({ method: 'POST' }),
    );
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({
      model: 'mimo-v2.5-tts',
      messages: [{ role: 'assistant', content: '你好' }],
      audio: { format: 'wav', voice: 'mimo_default' },
    });
    expect(Buffer.from(result.audio).toString()).toBe('wav-audio');
    expect(result.format).toBe('wav');
  });

  it('transcribes audio through chat completions input_audio content', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: '你好，这是识别结果。' } }],
      }),
    });

    const result = await transcribeAudio(
      {
        providerId: 'xiaomi-mimo-asr',
        apiKey: 'tp-test',
        baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1/',
        modelId: 'mimo-v2.5-asr',
        language: 'zh',
      },
      Buffer.from('audio'),
    );

    expect(mockFetch).toHaveBeenCalledWith(
      'https://token-plan-cn.xiaomimimo.com/v1/chat/completions',
      expect.objectContaining({ method: 'POST' }),
    );
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.model).toBe('mimo-v2.5-asr');
    expect(body.messages[0].content[0].type).toBe('input_audio');
    expect(body.messages[0].content[0].input_audio.data).toBe(
      `data:audio/mpeg;base64,${Buffer.from('audio').toString('base64')}`,
    );
    expect(body.asr_options).toEqual({ language: 'zh' });
    expect(result).toEqual({ text: '你好，这是识别结果。' });
  });
});
