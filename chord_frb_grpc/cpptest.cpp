/*
 *
 * Copyright 2015 gRPC authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

#include <grpcpp/grpcpp.h>

#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "absl/flags/flag.h"
#include "absl/flags/parse.h"

#include "frb_sifter.grpc.pb.h"

ABSL_FLAG(std::string, target, "localhost:50051", "Server address");

using grpc::Channel;
using grpc::ClientContext;
using grpc::Status;

struct frb_event {
    int32_t beam_id;
    int64_t fpga_timestamp;
    float dm;
    float dm_error;
    float snr;
    float rfi_prob;
};

class FrbSifterClient {
public:
    FrbSifterClient(std::shared_ptr<Channel> channel)
        : stub_(FrbSifter::NewStub(channel)) {}

    bool CheckConfiguration(const std::string& config_yaml) {
        ConfigMessage msg;
        msg.set_yaml(config_yaml);
        ConfigReply reply;
        reply.set_ok(false);

        ClientContext context;
        Status status = stub_->CheckConfiguration(&context, msg, &reply);
        if (status.ok()) {
            return reply.ok();
        } else {
            std::cout << status.error_code() << ": " << status.error_message()
                      << std::endl;
            return false;
        }
    }

    std::string FrbEvents(std::vector<frb_event> events, bool injections,
                          int32_t beamset_id, int64_t chunk_fpga_count) {
        FrbEventsMessage msg;
        FrbEventsReply reply;
        msg.set_has_injections(injections);
        msg.set_beam_set_id(beamset_id);
        msg.set_chunk_fpga_count(chunk_fpga_count);
        for (auto e : events) {
            FrbEvent* ee = msg.add_events();
            ee->set_beam_id(e.beam_id);
            ee->set_fpga_timestamp(e.fpga_timestamp);
            ee->set_dm(e.dm);
            ee->set_dm_error(e.dm_error);
            ee->set_snr(e.snr);
            ee->set_rfi_prob(e.rfi_prob);
        }
        reply.set_ok(false);

        ClientContext context;
        Status status = stub_->FrbEvents(&context, msg, &reply);
        if (status.ok()) {
            return reply.message();
        } else {
            std::cout << status.error_code() << ": " << status.error_message()
                      << std::endl;
            std::cout << "Message: " << reply.message() << std::endl;
            return "";
        }
    }

private:
  std::unique_ptr<FrbSifter::Stub> stub_;

};

int main(int argc, char** argv) {
  absl::ParseCommandLine(argc, argv);
  // Instantiate the client. It requires a channel, out of which the actual RPCs
  // are created. This channel models a connection to an endpoint specified by
  // the argument "--target=" which is the only expected argument.
  std::string target_str = absl::GetFlag(FLAGS_target);
  // We indicate that the channel isn't authenticated (use of
  // InsecureChannelCredentials()).

  FrbSifterClient sifter(grpc::CreateChannel(target_str, grpc::InsecureChannelCredentials()));

  std::string config_yaml("ceci n'est pas yaml");
  bool ok = sifter.CheckConfiguration(config_yaml);
  std::cout << "Sifter config check: " << ok << std::endl;

  bool injections = false;
  int32_t beamset_id = 0;
  int64_t chunk_fpga_count = 0;
  std::vector<frb_event> events;
  frb_event e;
  e.beam_id = 42;
  e.fpga_timestamp = 3700;
  e.dm = 900.0;
  e.dm_error = 2.0;
  e.snr = 9.5;
  e.rfi_prob = 0.1;
  events.push_back(e);

  e.beam_id = 44;
  e.snr = 8.0;
  events.push_back(e);

  std::string result = sifter.FrbEvents(events, injections, beamset_id, chunk_fpga_count);
  std::cout << "Result: " << result << std::endl;

  return 0;
}
