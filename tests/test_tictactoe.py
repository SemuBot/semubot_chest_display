"""Tic-tac-toe rules, the robot's play and the real Tk game screen."""
import os
import time
import tkinter as tk
from unittest.mock import MagicMock, patch

import app as ui
import tictactoe


def never_loses(board):
    """Try every visitor move against the perfect robot; True if the visitor can never win."""
    for index in tictactoe.free_squares(board):
        trial = board.copy()
        trial[index] = "X"
        if tictactoe.winner(trial) == "X":
            return False
        if tictactoe.winner(trial):
            continue
        trial[tictactoe.robot_move(trial)] = "O"
        if not tictactoe.winner(trial) and not never_loses(trial):
            return False
    return True


def test_rules_and_robot():
    assert tictactoe.winner(["X", "X", "X", "", "", "", "", "", ""]) == "X"
    assert tictactoe.winner(["O", "", "", "", "O", "", "", "", "O"]) == "O"
    assert tictactoe.winner(["X", "O", "X", "X", "O", "O", "O", "X", "X"]) == "draw"
    assert tictactoe.winner([""] * 9) is None
    assert tictactoe.robot_move(["O", "O", "", "X", "X", "", "", "", ""]) == 2  # wins rather than blocks
    assert tictactoe.robot_move(["X", "X", "", "", "O", "", "", "", ""]) == 2  # blocks
    assert never_loses([""] * 9)
    moves = {tictactoe.robot_move(["X", "", "", "", "", "", "", "", ""], mistakes=1.0) for _ in range(200)}
    assert len(moves) > 3  # easy mode really plays random squares


def test_game_screen():
    if not os.environ.get("DISPLAY"):
        from unittest import SkipTest
        raise SkipTest("Tk game checks need a graphical display")
    root = tk.Tk()
    root.withdraw()
    ros = MagicMock()
    ros.node = None
    with patch.object(ui, 'RobotRos', return_value=ros):
        app = ui.ChestDisplayApp(root, 1024, 600)
        app.show_games()
        next(w for w in root.winfo_children()
             if isinstance(w, tk.Button) and w.cget('text') == 'Trips-traps-trull').invoke()
        cells = [w for w in root.winfo_children() if isinstance(w, tk.Button) and w.cget('text') == '']
        assert len(cells) == 9
        ros.say.assert_called_once_with(ui.TICTACTOE_SPEECH["start"][0])
        app.tictactoe_mistakes = 0.0
        cells[4].invoke()
        cells[4].invoke()  # an occupied square is ignored
        assert cells[4].cget('text') == 'X'
        deadline = time.monotonic() + 3
        while sum(c.cget('text') == 'O' for c in cells) < 1 and time.monotonic() < deadline:
            root.update()
        assert sum(c.cget('text') == 'O' for c in cells) == 1
        with patch.object(ui, 'GAME_IDLE_SECONDS', 0):
            deadline = time.monotonic() + 3
            while cells[0].winfo_exists() and time.monotonic() < deadline:
                root.update()
        assert not cells[0].winfo_exists()  # idle timeout went back to the chest image
        app.close()


if __name__ == '__main__':
    test_rules_and_robot()
    test_game_screen()
    print('PASS: rules, perfect robot never loses, easy mode, game screen, idle timeout')
