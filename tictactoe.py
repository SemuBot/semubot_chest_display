"""Tic-tac-toe rules and the robot's moves. A board is a list of 9 'X', 'O' or ''."""

import random

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def winner(board):
    """'X' or 'O' for three in a row, 'draw' for a full board, otherwise None."""
    for a, b, c in LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None if "" in board else "draw"


def free_squares(board):
    return [index for index, value in enumerate(board) if not value]


def _score(board, turn, me, depth):
    """Minimax score for `me`: quicker wins and slower losses score higher."""
    result = winner(board)
    if result == me:
        return 10 - depth
    if result == "draw":
        return 0
    if result:
        return depth - 10
    other = "O" if turn == "X" else "X"
    scores = []
    for index in free_squares(board):
        board[index] = turn
        scores.append(_score(board, other, me, depth + 1))
        board[index] = ""
    return max(scores) if turn == me else min(scores)


def robot_move(board, me="O", mistakes=0.0):
    """Best square for `me`; with probability `mistakes` a random free square instead."""
    free = free_squares(board)
    if random.random() < mistakes:
        return random.choice(free)
    other = "O" if me == "X" else "X"
    scores = {}
    for index in free:
        board[index] = me
        scores[index] = _score(board, other, me, 1)
        board[index] = ""
    best = max(scores.values())
    # Pick among equally good squares so the robot doesn't play the same game every time.
    return random.choice([index for index, score in scores.items() if score == best])
