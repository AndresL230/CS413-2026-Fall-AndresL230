(*
** Per-function test cases for original/queens.dats.
**
** `make expected` compiles this from inside build/, where queens_lib.dats is
** a copy of the original with main0 removed, and saves the output as
** tests/expected/cases.out. tests/py/cases.py prints the same lines for the
** Python translation. See TESTING.md for what each case checks.
**
** Every case prints:
**   ### <id> <call, written in Python syntax>
**   <whatever the function printed>
**   => <return value>
** The header is built from the real arguments, and the function is called in
** its own statement before its result is printed.
*)

(* ****** ****** *)
//
#include "queens_lib.dats"
//
(* ****** ****** *)

fn show_bool (b: bool): void =
  print_string (if b then "true" else "false")

fn show_board (bd: int8): void =
  print! ("(", bd.0, ", ", bd.1, ", ", bd.2, ", ", bd.3, ", ",
          bd.4, ", ", bd.5, ", ", bd.6, ", ", bd.7, ")")

(* ****** ****** *)

// print_dots never ends its line, so this runner does.
fn case_print_dots (id: string, i: int): void = {
  val () = print! ("### ", id, " print_dots(", i, ")\n")
  val () = print_dots (i)
  val () = print! ("\n=> ()\n")
}

fn case_print_row (id: string, i: int): void = {
  val () = print! ("### ", id, " print_row(", i, ")\n")
  val () = print_row (i)
  val () = print! ("=> ()\n")
}

fn case_print_board (id: string, bd: int8): void = {
  val () = print! ("### ", id, " print_board(")
  val () = show_board (bd)
  val () = print! (")\n")
  val () = print_board (bd)
  val () = print! ("=> ()\n")
}

fn case_board_get (id: string, bd: int8, i: int): void = {
  val () = print! ("### ", id, " board_get(")
  val () = show_board (bd)
  val () = print! (", ", i, ")\n")
  val r = board_get (bd, i)
  val () = print! ("=> ", r, "\n")
}

fn case_board_set (id: string, bd: int8, i: int, j: int): void = {
  val () = print! ("### ", id, " board_set(")
  val () = show_board (bd)
  val () = print! (", ", i, ", ", j, ")\n")
  val r = board_set (bd, i, j)
  val () = print! ("=> ")
  val () = show_board (r)
  val () = print! ("\n")
}

fn case_safety_test1 (id: string, i0: int, j0: int, i: int, j: int): void = {
  val () = print! ("### ", id, " safety_test1(", i0, ", ", j0, ", ", i, ", ", j, ")\n")
  val r = safety_test1 (i0, j0, i, j)
  val () = print! ("=> ")
  val () = show_bool (r)
  val () = print! ("\n")
}

fn case_safety_test2 (id: string, i0: int, j0: int, bd: int8, i: int): void = {
  val () = print! ("### ", id, " safety_test2(", i0, ", ", j0, ", ")
  val () = show_board (bd)
  val () = print! (", ", i, ")\n")
  val r = safety_test2 (i0, j0, bd, i)
  val () = print! ("=> ")
  val () = show_bool (r)
  val () = print! ("\n")
}

fn case_search (id: string, bd: int8, i: int, j: int, nsol: int): void = {
  val () = print! ("### ", id, " search(")
  val () = show_board (bd)
  val () = print! (", ", i, ", ", j, ", ", nsol, ")\n")
  val r = search (bd, i, j, nsol)
  val () = print! ("=> ", r, "\n")
}

(* ****** ****** *)

implement
main0 () = {
//
val sol1: int8 = (0, 4, 7, 5, 2, 6, 1, 3) // Solution #1
val zeros: int8 = (0, 0, 0, 0, 0, 0, 0, 0)
//
val () = case_print_dots ("P1", 0)
val () = case_print_dots ("P2", 3)
val () = case_print_dots ("P3", ~3)
val () = case_print_row ("P4", 0)
val () = case_print_row ("P5", 7)
val () = case_print_board ("P6", sol1)
//
val () = case_board_get ("G1.0", sol1, 0)
val () = case_board_get ("G1.1", sol1, 1)
val () = case_board_get ("G1.2", sol1, 2)
val () = case_board_get ("G1.3", sol1, 3)
val () = case_board_get ("G1.4", sol1, 4)
val () = case_board_get ("G1.5", sol1, 5)
val () = case_board_get ("G1.6", sol1, 6)
val () = case_board_get ("G1.7", sol1, 7)
val () = case_board_get ("G2", sol1, 8)
val () = case_board_get ("G3", sol1, ~1)
//
val () = case_board_set ("S1", sol1, 3, 6)
val () = case_board_set ("S2", sol1, 7, 0)
val () = case_board_set ("S3", sol1, 8, 5)
val () = case_board_set ("S4", sol1, ~1, 5)
//
val () = case_safety_test1 ("T1", 0, 0, 1, 2)
val () = case_safety_test1 ("T2", 0, 3, 5, 3)
val () = case_safety_test1 ("T3", 2, 2, 5, 5)
val () = case_safety_test1 ("T4", 5, 1, 2, 4)
val () = case_safety_test1 ("T5", 3, 3, 3, 3)
val () = case_safety_test2 ("T6", 7, 3, sol1, 6)
val () = case_safety_test2 ("T7", 3, 4, sol1, 2)
val () = case_safety_test2 ("T8", 0, 5, zeros, ~1)
//
val () = case_search ("R2", zeros, 0, 8, 0)
val () = case_search ("R3", zeros, 0, 7, 10)
val () = case_search ("R4", zeros, 1, 0, 0)
val () = case_search ("R5.0", zeros, 0, 0, 0)
val () = case_search ("R5.1", zeros, 0, 1, 0)
val () = case_search ("R5.2", zeros, 0, 2, 0)
val () = case_search ("R5.3", zeros, 0, 3, 0)
val () = case_search ("R5.4", zeros, 0, 4, 0)
val () = case_search ("R5.5", zeros, 0, 5, 0)
val () = case_search ("R5.6", zeros, 0, 6, 0)
val () = case_search ("R5.7", zeros, 0, 7, 0)
//
} (* end of [main0] *)

(* ****** ****** *)

(* end of [cases.dats] *)
