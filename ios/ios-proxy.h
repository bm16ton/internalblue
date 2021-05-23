//
//  ios-proxy.h
//  ios-proxy
//
//  Copyright © 2019 ttdennis. All rights reserved.
//

#ifndef ios_proxy_h
#define ios_proxy_h

#include <stdio.h>


#define IOAOSSKYSETCHANNELSPEC 0x800C5414
#define IOAOSSKYGETCHANNELUUID 0x40105412

#define CTLIOCGINFO 0xC0644E03

typedef struct ctl_info {
    uint32_t ctl_id;
    char ctl_name[96];
} ctl_info_t;

int connect_bt_device();
int create_server(int port);
int wait_for_connection(int server_fd);
void proxy_bt_socket(int client, int bt);

#endif /* ios_proxy_h */
