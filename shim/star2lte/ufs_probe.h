#pragma once
#include <stdint.h>

void ufs_probe(void (*kv)(const char *, uint64_t), void (*out)(const char *),
	       uintptr_t dma_base);

/* Write the loader log to the LDRLOG area below the kernel ring in USERDATA. */
int ufs_log_write(const uint8_t *text, uint32_t len);
