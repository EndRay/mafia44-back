class GameException(Exception):
    details = None
    code = 400


class UserNotFoundException(GameException):
    details = "User not found"
    code = 404


class RoomNotFoundException(GameException):
    details = "Room not found"
    code = 404


class RoomAlreadyExistsException(GameException):
    details = "Room already exists"
    code = 409


class UserAlreadyInRoomException(GameException):
    details = "User already in room"
    code = 400


class UserNotCreatorException(GameException):
    details = "User is not the creator of the room"
    code = 403


class CreatorCannotLeaveRoomException(GameException):
    details = "Creator cannot leave the room"
    code = 400


class RoomFullException(GameException):
    details = "Room is full"
    code = 403


class GameAlreadyStartedException(GameException):
    details = "Game has already started"
    code = 409


class GameNotStartedException(GameException):
    details = "Game has not started"
    code = 400


class UserNotInRoomException(GameException):
    details = "User not in room"
    code = 403


class GameNotFinishedException(GameException):
    details = "Game not finished"
    code = 400


class InvalidSelectedCardsException(GameException):
    details = "Invalid selected cards"
    code = 400