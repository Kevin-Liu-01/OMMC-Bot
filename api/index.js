const {
  InteractionResponseType,
  InteractionType,
  verifyKey,
} = require("discord-interactions");
const getRawBody = require("raw-body");

// const SLAP_COMMAND = {
//   name: 'Slap',
//   description: 'Sometimes you gotta slap a person with a large trout',
//   options: [
//     {
//       name: 'user',
//       description: 'The user to slap',
//       type: 6,
//       required: true,
//     },
//   ],
// };

const INVITE_COMMAND = {
  name: "Invite",
  description: "Get an invite link to add the bot to your server",
};

const SUPPORT_COMMAND = {
  name: "Support",
  description: "Like this bot? Support its inspiration!",
};

const PROBLEM_COMMAND = {
  name: "Problem",
  description: "Get the POTD",
};

const INVITE_URL = `https://discord.com/oauth2/authorize?client_id=${process.env.APPLICATION_ID}&scope=applications.commands`;

/**
 * Gotta see someone 'bout a trout
 * @param {VercelRequest} request
 * @param {VercelResponse} response
 */
module.exports = async (request, response) => {
  if (request.method === "POST") {
    const signature = request.headers["x-signature-ed25519"];
    const timestamp = request.headers["x-signature-timestamp"];
    const rawBody = JSON.stringify(request.body);

    const isValidRequest = verifyKey(
      rawBody,
      signature,
      timestamp,
      process.env.PUBLIC_KEY
    );

    if (!isValidRequest) {
      console.error("Invalid Request");
      return response.status(401).send({ error: "Bad request signature " });
    }

    const message = request.body;

    if (message.type === InteractionType.PING) {
      console.log("Handling Ping request");
      response.send({
        type: InteractionResponseType.PONG,
      });
    } else if (message.type === InteractionType.APPLICATION_COMMAND) {
      switch (message.data.name.toLowerCase()) {
        // case SLAP_COMMAND.name.toLowerCase():
        //   response.status(200).send({
        //     type: 4,
        //     data: {
        //       content: `*<@${message.member.user.id}> slaps <@${message.data.options[0].value}> around a bit with a large trout*`,
        //     },
        //   });
        //   console.log('Slap Request');
        //   break;
        case INVITE_COMMAND.name.toLowerCase():
          response.status(200).send({
            type: 4,
            data: {
              content: INVITE_URL,
              flags: 64,
            },
          });
          console.log("Invite request");
          break;
        case SUPPORT_COMMAND.name.toLowerCase():
          response.status(200).send({
            type: 4,
            data: {
              content:
                "Thanks for using OMMC bot! It is based off of Ian Mitchell's Vercel bot tutorial. You can support him at https://github.com/sponsors/ianmitchell",
              flags: 64,
            },
          });
          console.log("Support request");
          break;
        default:
          console.error("Unknown Command");
          response.status(400).send({ error: "Unknown Type" });
          break;
      }
    } else {
      console.error("Unknown Type");
      response.status(400).send({ error: "Unknown Type" });
    }
  }
};
