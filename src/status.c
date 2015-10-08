/*
    This file is a part of saldl.

    Copyright (C) 2014-2015 Mohammad AlSaleh <CE.Mohammad.AlSaleh at gmail.com>
    https://saldl.github.io

    saldl is free software: you can redistribute it and/or modify
    it under the terms of the Affero GNU General Public License as
    published by the Free Software Foundation.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    Affero GNU General Public License for more details.

    You should have received a copy of the Affero GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include "events.h"
#include "utime.h"

static inline void colorset(char *ptr, char val, size_t size) {
  while (size) {
    switch (val) {
      case CH_PRG_NOT_STARTED:
      case CH_PRG_QUEUED:
        strncpy(ptr,error_color,strlen(error_color));
        ptr+= strlen(error_color);
        memset(ptr,val,1);
        ptr++;
        break;
      case CH_PRG_STARTED:
        strncpy(ptr,warn_color,strlen(warn_color));
        ptr+= strlen(warn_color);
        memset(ptr,val,1);
        ptr++;
        break;
      case CH_PRG_FINISHED:
        strncpy(ptr,info_color,strlen(info_color));
        ptr+= strlen(info_color);
        memset(ptr,val,1);
        ptr++;
        break;
      case CH_PRG_MERGED:
        strncpy(ptr,ok_color,strlen(ok_color));
        ptr+= strlen(ok_color);
        memset(ptr,val,1);
        ptr++;
        break;
    }
    strncpy(ptr,end,strlen(end));
    ptr+= strlen(end);
    size--;
  }
}

static void status_update_cb(evutil_socket_t fd, short what, void *arg) {
  info_s *info_ptr = arg;
  saldl_params *params_ptr = info_ptr->params;

  progress_s *p = &(info_ptr->global_progress);
  chunks_progress_s *chsp = &(p->chunks_progress);
  status_s *status_ptr = &info_ptr->status;
  event_s *ev_status = &info_ptr->ev_status;

  double params_refresh = params_ptr->status_refresh_interval;
  double refresh_interval = params_refresh ? params_refresh : SALDL_DEF_STATUS_REFRESH_INTERVAL;

  size_t c_char_size = status_ptr->c_char_size;
  char *chunks_status = status_ptr->chunks_status;
  size_t *lines = &status_ptr->lines;


  /* Update lines in case tty width changes */
  int cols = tty_width() >= 0 ? tty_width() : 0;
  *lines = status_ptr->lines = cols ? info_ptr->chunk_count / cols + !!(info_ptr->chunk_count % cols) + 8 + !!p->initial_complete_size : 0 ; /*  +n: number of extra status lines */

  debug_event_msg(FN, "callback no. %ju for triggered event %s, with what %d", ++ev_status->num_of_calls, str_EVENT_FD(fd) , what);


  /* We check if the merge loop is already de-initialized to not lose status of any merged chunks */
  if ( (info_ptr->session_status == SESSION_INTERRUPTED || !exist_prg(info_ptr, PRG_MERGED, false) ) && info_ptr->ev_merge.event_status < EVENT_INIT) {
    events_deactivate(ev_status);
  }

  p->curr = saldl_utime();
  p->dur = p->curr - p->start;
  p->curr_dur = p->curr - p->prev;
  global_progress_update(info_ptr, false);

  /* Skip if --no-status */
  if (info_ptr->params->no_status) {
    return;
  }

  off_t session_complete_size = saldl_max_o(p->complete_size - p->initial_complete_size, 0); // Don't go -ve on reconnects
  off_t session_size = info_ptr->file_size - p->initial_complete_size;
  off_t rem_size =  info_ptr->file_size - p->complete_size;
  
  /* Calculate rates, remaining times */
  if (p->dur >= SALDL_STATUS_INITIAL_INTERVAL) {
    p->rate = session_complete_size/p->dur;
    p->rem = p->rate ? rem_size/p->rate : INT64_MAX;
  }

  if (p->curr_dur >= refresh_interval ||
      (p->dur  >= SALDL_STATUS_INITIAL_INTERVAL && p->dur < refresh_interval) ||
      p->complete_size == info_ptr->file_size) {
    off_t curr_complete_size = saldl_max_o(p->complete_size - p->dlprev, 0); // Don't go -ve on reconnects
    p->curr_rate = curr_complete_size/p->curr_dur;
    p->curr_rem = p->curr_rate ? rem_size/p->curr_rate : INT64_MAX;

    p->prev = p->curr;
    p->dlprev = p->complete_size;

    /* Set progress_status */
    for (size_t counter = 0; counter < info_ptr->chunk_count; counter++) {
      colorset(chunks_status+(counter*c_char_size), '0' + info_ptr->chunks[counter].progress, 1);
    }

    main_info_msg("Chunk progress", " ");
    status_msg("Merged", "          \t %zu / %zu (+%zu finished)",
        chsp->merged, info_ptr->chunk_count, chsp->finished);
    status_msg("Started", "         \t %zu / %zu (%zu empty)",
        chsp->started, info_ptr->chunk_count, chsp->empty_started);
    status_msg("Not started", "     \t %zu / %zu ((+%zu queued)",
        chsp->not_started, info_ptr->chunk_count, chsp->queued);
    status_msg("Size complete", "   \t %.2f%s / %.2f%s (%.2f%c)",
        human_size(p->complete_size), human_size_suffix(p->complete_size),
        human_size(info_ptr->file_size), human_size_suffix(info_ptr->file_size),
        PCT(p->complete_size, info_ptr->file_size), '%');
    if (p->initial_complete_size) {
      status_msg("Session complete", "\t %.2f%s / %.2f%s (%.2f%c)",
          human_size(session_complete_size), human_size_suffix(session_complete_size),
          human_size(session_size), human_size_suffix(session_size),
          PCT(session_complete_size, session_size), '%');
    }
    status_msg("Rate", "            \t %.2f%s/s : %.2f%s/s",
        human_size(p->rate), human_size_suffix(p->rate),
        human_size(p->curr_rate), human_size_suffix(p->curr_rate));

    status_msg("Remaining", "       \t %.1fs : %.1fs", p->rem, p->curr_rem);
    status_msg("Duration", "        \t %.1fs", p->dur);

    fprintf(stderr,"%s%s%s\n", erase_screen_after, chunks_status, ret_char);
    saldl_fputs_count(*lines, up, stderr, "stderr");
  }
}

void* status_display(void *void_info_ptr) {
  /* prep  */
  info_s *info_ptr = void_info_ptr;
  status_s *status_ptr = &info_ptr->status;

  /* Thread entered */
  SALDL_ASSERT(info_ptr->ev_status.event_status == EVENT_NULL);
  info_ptr->ev_status.event_status = EVENT_THREAD_STARTED;

  /* initialize status */
  size_t c_char_size = status_ptr->c_char_size = strlen(ok_color) +strlen(end) + 1;
  char *chunks_status = status_ptr->chunks_status = saldl_calloc(info_ptr->chunk_count*c_char_size + 1, sizeof(char)); /* Sometimes, an extra char is shown/read(valgrind) at the end without the extra bit, maybe due to lack of space for \0 */
  int cols = tty_width() >= 0 ? tty_width() : 0;
  size_t lines = status_ptr->lines = cols ? info_ptr->chunk_count / cols + !!(info_ptr->chunk_count % cols) + 9 + !!info_ptr->global_progress.initial_complete_size : 0 ; /*  +n: number of extra status lines */

  /* initial chunks_status */
  colorset(chunks_status, '0', info_ptr->chunk_count);

  /* event loop */
  events_init(&info_ptr->ev_status, status_update_cb, info_ptr, EVENT_STATUS);

  SALDL_ASSERT(info_ptr->global_progress.initialized);

  if (info_ptr->session_status != SESSION_INTERRUPTED && exist_prg(info_ptr, PRG_MERGED, false)) {
    debug_msg(FN, "Start ev_status loop.");
    events_activate(&info_ptr->ev_status);
  }

  /* Event loop exited */
  events_deinit(&info_ptr->ev_status);

  /* finalize and cleanup */
  if (!info_ptr->params->no_status) {
    saldl_fputs_count(lines, "\n", stderr, "stderr");
  }

  SALDL_FREE(chunks_status);
  return info_ptr;
}

/* vim: set filetype=c ts=2 sw=2 et spell foldmethod=syntax: */
