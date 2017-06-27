
Limits @ 170623
-------------------------------------
No priority, no data management, no subsampling

7 ch x 500 samp@10kHz -> x
5 ch x 400 samp@10kHz -> x (17s)
1 ch x 300 samp@10Hz  -> x (9s)
1 ch x 350            -> x (30s)
1 ch x 370            -> x (17s)
1 ch x 380            -> ok (<60s)
1 ch x 400            -> ok (<60s) x 2
2 ch x 380            -> x (22s)
2 ch x 400            -> ok (<60s)
3 ch x 400            -> x (20s)
3 ch x 450            -> ok (<60s)
3 ch x 500            -> ok (<60s)
4 ch x 450            -> x (17s)
4 ch x 500            -> ok (<60s)
5 ch x 500            -> x (15s)
5 ch x 600            -> ok (<60s)
6 ch x 600            -> x (23s)
6 ch x 700            -> x (23s)
6 ch x 800            -> x (14s)
6 ch x 900            -> ok (<60s)
6 ch x 1000           -> ok (<60s)
7 ch x 900            -> ok (<60s)
8 ch x 900            -> x (22s)
8 ch x 1000           -> ok (<60s)


Limits @ 170626-1
---------------------

- with priority
- no numpy wrapping
- no data management
- no subsampling
- at 10khz

1ch: >=380
2ch: >=380
4ch: >=470
8ch: >=700

Better power on large channel numbers.
Almost no difference for baseline requirements.


Limits @ 170626-2
--------------------

- with priority
- numpy copy in C
- no ring buffer
- no data management
- at 10kHz

1ch: >=370
2ch: >=380
4ch: >=470
8ch: >=700

Really slight change on the baseline requirement.


Limits @ 170627
-------------------

- with priority
- numpy buffer in C
- no ring buffer
- no data management
- at 10 kHz

1ch: >=370
2ch: >=370
4ch: >=460
8ch: >=690

Slight changes on channel-number dependency.
Data management on the user side should be the problem.
