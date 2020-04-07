"""
gtp_connection.py
Module for playing games of Go using GoTextProtocol

Parts of this code were originally based on the gtp module 
in the Deep-Go project by Isaac Henrion and Amos Storkey 
at the University of Edinburgh.

"""






import traceback
from sys import stdin, stdout, stderr
from board_util import GoBoardUtil, BLACK, WHITE, EMPTY, BORDER, PASS, \
                       MAXSIZE, coord_to_point
import numpy as np
import re
import signal

class GtpConnection():

    def __init__(self, go_engine, board, debug_mode = False):
        self.hash = {}
       
        self.hash_size = 100000
        
        """
        Manage a GTP connection for a Go-playing engine

        Parameters
        ----------
        go_engine:
            a program that can reply to a set of GTP commandsbelow
        board: 
            Represents the current board state.
        """
        self._debug_mode = debug_mode
        self.go_engine = go_engine
        self.board = board
        self._timelimit = 5
        self._toPlay = 2 # black play first as defalut
        self.commands = {
            "protocol_version": self.protocol_version_cmd,
            "quit": self.quit_cmd,
            "name": self.name_cmd,
            "boardsize": self.boardsize_cmd,
            "showboard": self.showboard_cmd,
            "clear_board": self.clear_board_cmd,
            "komi": self.komi_cmd,
            "version": self.version_cmd,
            "known_command": self.known_command_cmd,
            "genmove": self.genmove_cmd,
            "list_commands": self.list_commands_cmd,
            "play": self.play_cmd,
            "legal_moves": self.legal_moves_cmd,
            "gogui-rules_game_id": self.gogui_rules_game_id_cmd,
            "gogui-rules_board_size": self.gogui_rules_board_size_cmd,
            "gogui-rules_legal_moves": self.gogui_rules_legal_moves_cmd,
            "gogui-rules_side_to_move": self.gogui_rules_side_to_move_cmd,
            "gogui-rules_board": self.gogui_rules_board_cmd,
            "gogui-rules_final_result": self.gogui_rules_final_result_cmd,
            "gogui-analyze_commands": self.gogui_analyze_cmd,
            "timelimit": self.timelimit,
            "solve": self.solve

        }

        # used for argument checking
        # values: (required number of arguments, 
        #          error message on argnum failure)
        self.argmap = {
            "boardsize": (1, 'Usage: boardsize INT'),
            "komi": (1, 'Usage: komi FLOAT'),
            "known_command": (1, 'Usage: known_command CMD_NAME'),
            "genmove": (1, 'Usage: genmove {w,b}'),
            "play": (2, 'Usage: play {b,w} MOVE'),
            "legal_moves": (1, 'Usage: legal_moves {w,b}')
        }
    
    def write(self, data):
        stdout.write(data) 

    def flush(self):
        stdout.flush()

    def start_connection(self):
        """
        Start a GTP connection. 
        This function continuously monitors standard input for commands.
        """


        line = stdin.readline()
        while line:
            self.get_cmd(line)
            line = stdin.readline()

    def get_cmd(self, command):
        """
        Parse command string and execute it
        """
        if len(command.strip(' \r\t')) == 0:
            return
        if command[0] == '#':
            return
        # Strip leading numbers from regression tests
        if command[0].isdigit():
            command = re.sub("^\d+", "", command).lstrip()

        elements = command.split()
        if not elements:
            return
        command_name = elements[0]; args = elements[1:]
        if self.has_arg_error(command_name, len(args)):
            return
        if command_name in self.commands:
            try:
                self.commands[command_name](args)
            except Exception as e:
                self.debug_msg("Error executing command {}\n".format(str(e)))
                self.debug_msg("Stack Trace:\n{}\n".
                               format(traceback.format_exc()))
                raise e
        else:
            self.debug_msg("Unknown command: {}\n".format(command_name))
            self.error('Unknown command')
            stdout.flush()

    def has_arg_error(self, cmd, argnum):
        """
        Verify the number of arguments of cmd.
        argnum is the number of parsed arguments
        """
        if cmd in self.argmap and self.argmap[cmd][0] != argnum:
            self.error(self.argmap[cmd][1])
            return True
        return False

    def debug_msg(self, msg):
        """ Write msg to the debug stream """
        if self._debug_mode:
            stderr.write(msg)
            stderr.flush()

    def error(self, error_msg):
        """ Send error msg to stdout """
        stdout.write('? {}\n\n'.format(error_msg))
        stdout.flush()

    def respond(self, response=''):
        """ Send response to stdout """
        stdout.write('= {}\n\n'.format(response))
        stdout.flush()

    def reset(self, size):
        """
        Reset the board to empty board of given size
        """
        self.board.reset(size)

    def board2d(self):
        return str(GoBoardUtil.get_twoD_board(self.board))
        
    def protocol_version_cmd(self, args):
        """ Return the GTP protocol version being used (always 2) """
        self.respond('2')

    def quit_cmd(self, args):
        """ Quit game and exit the GTP interface """
        self.respond()
        exit()

    def name_cmd(self, args):
        """ Return the name of the Go engine """
        self.respond(self.go_engine.name)

    def version_cmd(self, args):
        """ Return the version of the  Go engine """
        self.respond(self.go_engine.version)

    def clear_board_cmd(self, args):
        """ clear the board """
        self.reset(self.board.size)
        self.respond()

    def boardsize_cmd(self, args):

        self.reset(int(args[0]))
        self.respond()

    def showboard_cmd(self, args):
        
        self.respond('\n' + self.board2d())

    def komi_cmd(self, args):

        self.go_engine.komi = float(args[0])
        self.respond()

    def known_command_cmd(self, args):

        if args[0] in self.commands:
            self.respond("true")
        else:
            self.respond("false")

    def list_commands_cmd(self, args):
    
        self.respond(' '.join(list(self.commands.keys())))

    def legal_moves_cmd(self, args):

        board_color = args[0].lower()
        color = color_to_int(board_color)
        moves = GoBoardUtil.generate_legal_moves(self.board, color)
        gtp_moves = []
        for move in moves:
            coords = point_to_coord(move, self.board.size)
            gtp_moves.append(format_point(coords))
        sorted_moves = ' '.join(sorted(gtp_moves))
        self.respond(sorted_moves)

    def timelimit(self, args):

        self._timelimit = int(args[0])
        self.respond()
        return

    def handler(self,signum, frame):
        raise TimeoutError

    def simulate(self, board,color): 
        current_player = board.current_player
        moves = GoBoardUtil.generate_legal_moves(board, current_player)
        if len(moves) == 0:
            return 3-current_player
        move=np.random.choice(moves)
        board.board[move] = current_player
        board.current_player = 3-current_player
        return self.simulate(board,color)



    def RandomMove(self, board, color):

        wins = 0
        for _ in range(self._timelimit//2):
            temp = board.copy()
            result = self.simulate(temp,color)
            if result == color:
                wins += 1
        return wins


    def solve(self, return_val=False):

        try:
            self.hash = {}
            
            current_depth = 0

            color = self.board.current_player
            moves = GoBoardUtil.generate_legal_moves(self.board, color)

         
            tempboard = self.board.copy()
            tempboard.current_player = 3 - color
            
            signal.signal(signal.SIGALRM, self.handler)
            signal.alarm(self._timelimit)

            if len(moves) >= 14:
                Tboard = self.board.copy()          
                moveWins = []
                for move in moves:
                    Tboard.board[move] = color
                    Tboard.current_player = 3-color
                    wins = self.RandomMove(Tboard,color)
                    moveWins.append(wins)
                    Tboard = self.board.copy()
                max_child = np.argmax(moveWins)
                signal.alarm(0)
                print("done")
                return moves[max_child]
                



            
            for move in moves:
                tempboard.board[move] = color
                
                # tempboard.play_move(move,color)
                # if self.minimax(tempboard,color,current_depth+1) == color:

                if not self.negamax(tempboard,1):
                    signal.alarm(0)
                   

                    move_coord = point_to_coord(move, tempboard.size)
                    move_as_string = format_point(move_coord)
                    
                   
                    if return_val ==True:
                        return (move)
                    
                    if self.board.current_player == 1:
                        self.respond("b "+ move_as_string.lower())
                    else:
                        self.respond("w "+ move_as_string.lower() )

                 

                    return None
                
                tempboard.board[move] = EMPTY
            signal.alarm(0)
            if return_val == True:
                return None

            if self.board.current_player == 1:
                self.respond("w")
            else:
                self.respond("b")


        except TimeoutError:
            # self.respond("unknown")
            signal.alarm(0)
            return None

        signal.alarm(0)
        return None

        
    def negamax(self,Tboard,depth):

       
            
        current_player = Tboard.current_player
        # moves = GoBoardUtil.generate_legal_moves(Tboard, current_player)

        

        moves = []
        temp = np.where(Tboard.board == 0)[0]
        
        for temp1 in temp:
            if Tboard.is_legal(temp1, current_player):
                moves.append(temp1)



        if moves == []:
            return False

        Tboard.current_player = 3 - current_player 
        for move in moves:
            Tboard.board[move] = current_player

            if depth <= 12:
                temp = self.hash.get(Tboard.board.tostring())
                if temp != None:

                    Tboard.board[move] = 0
                    if temp == current_player:
                        Tboard.current_player = current_player
                        return True
                    else:
                        continue
                
            if not self.negamax(Tboard,depth+1):
        
                Tboard.current_player = current_player

                if depth <= 12:
                    self.hash[Tboard.board.tostring()] = current_player
                Tboard.board[move] = 0

                return True
            if depth <= 12:
                self.hash[Tboard.board.tostring()] = 3-current_player
            Tboard.board[move] =  0
      
        Tboard.current_player = current_player
        return False

   

    def play_cmd(self, args):
        """
        play a move args[1] for given color args[0] in {'b','w'}
        """
        try:
            board_color = args[0].lower()
            board_move = args[1]
            if board_color != "b" and board_color !="w":
                self.respond("illegal move: \"{}\" wrong color".format(board_color))
                return
            color = color_to_int(board_color)
            if args[1].lower() == 'pass':
                self.respond("illegal move: \"{} {}\" wrong coordinate".format(args[0], args[1]))
                return
            coord = move_to_coord(args[1], self.board.size)
            if coord:
                move = coord_to_point(coord[0],coord[1], self.board.size)
            else:
                self.error("Error executing move {} converted from {}"
                           .format(move, args[1]))
                return
            if not self.board.play_move(move, color):
                self.respond("illegal move: \"{} {}\" ".format(args[0], board_move))
                return
            else:
                self.debug_msg("Move: {}\nBoard:\n{}\n".
                                format(board_move, self.board2d()))
            self.respond()
        except Exception as e:
            self.respond('illegal move: \"{} {}\" {}'.format(args[0], args[1], str(e)))

    def genmove_cmd(self, args):
        """
        Generate a move for the color args[0] in {'b', 'w'}, for the game of gomoku.
        """
        board_color = args[0].lower()
        color = color_to_int(board_color)
     
        
        
        ans= self.solve(True)
     

       

        
        
        if ans != None:
            self.board.play_move(ans, color)
            move_coord = point_to_coord(ans, self.board.size)
            move_as_string = format_point(move_coord)
            self.respond(move_as_string)
            return
        else:


            move = GoBoardUtil.generate_legal_moves(self.board,color)
            if move == []:
                self.respond("resign")
                return
            move_coord = point_to_coord(move[0], self.board.size)
            move_as_string = format_point(move_coord)

            
            self.board.play_move(move[0],color)
            self.respond(move_as_string)


    def gogui_rules_game_id_cmd(self, args):
        self.respond("nogo")
    
    def gogui_rules_board_size_cmd(self, args):
        self.respond(str(self.board.size))
    
    def legal_moves_cmd(self, args):
        """
            List legal moves for color args[0] in {'b','w'}
            """
        board_color = args[0].lower()
        color = color_to_int(board_color)
        moves = GoBoardUtil.generate_legal_moves(self.board, color)
        gtp_moves = []
        for move in moves:
            coords = point_to_coord(move, self.board.size)
            gtp_moves.append(format_point(coords))
        sorted_moves = ' '.join(sorted(gtp_moves))
        self.respond(sorted_moves)

    def gogui_rules_legal_moves_cmd(self, args):
        empties = self.board.get_empty_points()
        color = self.board.current_player
        legal_moves = []
        for move in empties:
            if self.board.is_legal(move, color):
                legal_moves.append(move)

        gtp_moves = []
        for move in legal_moves:
            coords = point_to_coord(move, self.board.size)
            gtp_moves.append(format_point(coords))
        sorted_moves = ' '.join(sorted(gtp_moves))
        self.respond(sorted_moves)
    
    def gogui_rules_side_to_move_cmd(self, args):
        color = "black" if self.board.current_player == BLACK else "white"
        self.respond(color)
    
    def gogui_rules_board_cmd(self, args):
        size = self.board.size
        str = ''
        for row in range(size-1, -1, -1):
            start = self.board.row_start(row + 1)
            for i in range(size):
                point = self.board.board[start + i]
                if point == BLACK:
                    str += 'X'
                elif point == WHITE:
                    str += 'O'
                elif point == EMPTY:
                    str += '.'
                else:
                    assert False
            str += '\n'
        self.respond(str)
    
    def gogui_rules_final_result_cmd(self, args):
        empties = self.board.get_empty_points()
        color = self.board.current_player
        legal_moves = []
        for move in empties:
            if self.board.is_legal(move, color):
                legal_moves.append(move)
        if not legal_moves:
            result = "black" if self.board.current_player == WHITE else "white"
        else:
            result = "unknown"
        self.respond(result)

    def gogui_analyze_cmd(self, args):
        self.respond("pstring/Legal Moves For ToPlay/gogui-rules_legal_moves\n"
                     "pstring/Side to Play/gogui-rules_side_to_move\n"
                     "pstring/Final Result/gogui-rules_final_result\n"
                     "pstring/Board Size/gogui-rules_board_size\n"
                     "pstring/Rules GameID/gogui-rules_game_id\n"
                     "pstring/Show Board/gogui-rules_board\n"
                     )

def point_to_coord(point, boardsize):
    """
    Transform point given as board array index 
    to (row, col) coordinate representation.
    Special case: PASS is not transformed
    """
    if point == PASS:
        return PASS
    else:
        NS = boardsize + 1
        return divmod(point, NS)

def format_point(move):
    """
    Return move coordinates as a string such as 'a1', or 'pass'.
    """
    column_letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    #column_letters = "abcdefghjklmnopqrstuvwxyz"
    if move == PASS:
        return "pass"
    row, col = move
    if not 0 <= row < MAXSIZE or not 0 <= col < MAXSIZE:
        raise ValueError
    return column_letters[col - 1]+ str(row) 
    
def move_to_coord(point_str, board_size):
    """
    Convert a string point_str representing a point, as specified by GTP,
    to a pair of coordinates (row, col) in range 1 .. board_size.
    Raises ValueError if point_str is invalid
    """
    if not 2 <= board_size <= MAXSIZE:
        raise ValueError("board_size out of range")
    s = point_str.lower()
    if s == "pass":
        return PASS
    try:
        col_c = s[0]
        if (not "a" <= col_c <= "z") or col_c == "i":
            raise ValueError
        col = ord(col_c) - ord("a")
        if col_c < "i":
            col += 1
        row = int(s[1:])
        if row < 1:
            raise ValueError
    except (IndexError, ValueError):
        # e.g. "a0"
        raise ValueError("wrong coordinate")
    if not (col <= board_size and row <= board_size):
        # e.g. "a20"
        raise ValueError("wrong coordinate")
    return row, col

def color_to_int(c):
    """convert character to the appropriate integer code"""
    color_to_int = {"b": BLACK , "w": WHITE, "e": EMPTY, 
                    "BORDER": BORDER}
    return color_to_int[c] 
