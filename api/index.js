const {
  InteractionResponseType,
  InteractionType,
  verifyKey,
} = require("discord-interactions");
// const getRawBody = require("raw-body");
const openai = require("openai");

openai.apiKey = process.env.OPENAI_API_KEY;

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
  description: "Get an invite link to add the bot to your server.",
};

const SUPPORT_COMMAND = {
  name: "Support",
  description: "Like this bot? Support its inspiration!",
};

const PROBLEM_COMMAND = {
  name: "Problem",
  description: "Get the POTD.",
};

const GPT3_COMMAND = {
  name: "gpt3",
  description: "Ask GPT-3 a question.",
  options: [
    {
      name: "question",
      description: "The question to ask GPT-3",
      type: 3,
      required: true,
    },
  ],
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
        case GPT3_COMMAND.name.toLowerCase():
          const question = message.data.options.find(
            (option) => option.name === "question"
          ).value;

          try {
            const gpt3Response = await openai.Completion.create({
              engine: "text-davinci-002",
              prompt: question,
              max_tokens: 100,
            });

            response.status(200).send({
              type: 4,
              data: {
                content: gpt3Response.choices[0].text.strip(),
              },
            });
          } catch (err) {
            console.error(err);
            response
              .status(500)
              .send({ error: "Error generating GPT-3 response" });
          }

          console.log("GPT-3 Request");
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
