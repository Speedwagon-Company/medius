import pino from "pino"

// Транспорт: пишем и в файл, и в консоль (для разработки)
export const logger = pino({
  level: 'info', // 'debug' для разработки
  transport: {
    targets: [
      {
        target: 'pino-pretty', // красивый вывод в консоль (опционально)
        level: 'info',
        options: { colorize: true }
      },
      {
        target: 'pino/file', // пишем в файл
        level: 'debug',
        options: { destination: './logs/app.log', mkdir: true } // папка создастся сама
      }
    ]
  }
});
