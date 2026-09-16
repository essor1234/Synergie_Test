# My Assumption

The system that Bright Path Learning Center is using is lack of connection between owners and Mid manager (Mai or the receptionist) with the tutors

This is why the owner have no idea why the students booked 2 slots at a time OR the receptionist cannot aleart and connect with the tutors on time. ---> The tutors cannot catch up with the latest changes, so they get lost if there are any changes come right up

The system is unified by the Receptionist --> This is why when she left, barely no one can jump in and handle the process

They'd need a system that

1. Simple to adapt with or without Mai (Cannot depends on one mid-manager for the whole system)
2. Allow Owner can real-time checking the running of the whole system --> Need a summarize UI
3. Real-time change + notificate for tutor if there is any sudden changes from the manager. --> a schedule???
4. Can intergrate their current spreadsheet system + Zalo chat to software system.
5.

# Questions

1. How the manager handle when the tutor need to cancle classes for that whole day? Since each tutors have maximum 6 classes/day only.
   ---> This gonna effect on the process of handle sudden situation or the flexible of the system, both software and real-life running. For example, 1. Change to another teacher if there is a free one 2. Reorganize another day if the teacher are available. 3. Organize a two students/class + reduce half price if student still wanna studay on that same day.

2. During exam season, should exam-season double bookings (two students with one tutor) be formalized as explicit group lessons?
   ----> This gonna effect on how to design a Lesson. its not only support 1-1 but now as a group if needed.

# Some catches that not clear right now

The owner did say that there are cases that students book two places at once. What book two places at once even mean?? ---> Is it book 2 classes(Teach + Room) at the same time?

# Extra Notes

# Phase 1 data decisions

- Every column in `tutors.csv` and `lessons_export.csv` has an explicit import destination.
- Original CSV values are retained in immutable raw tables. Operational empty `cancelled_at` and `note` values become `None`.
- Lesson start times use `Asia/Bangkok`; every stored lesson and cancellation timestamp includes timezone information.
- `L009` and `L010` remain separate raw rows and map to one two-student operational lesson only because `group_resolutions.json` declares that resolution.
- Student IDs are deterministic internal hashes of the exact source names. They are not presented as fields supplied by the spreadsheet.
- Only observed rooms `R1`, `R2`, and `R3` are seeded.
- Tutor phone values are stored exactly as text but remain outside the assessment API and UI.
