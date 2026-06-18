export class InvalidCmdException extends Error {
  constructor(message: string = "Invalid command or subcommand") {
    super(message);

    this.name = "InvalidCmdException";

    Object.setPrototypeOf(this, InvalidCmdException.prototype);
  }
}
