from __future__ import annotations

import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter

from .ppo_agent import Agent

def train_ppo(
    envs,
    total_timesteps: int = 200_000,
    learning_rate: float = 2.5e-4,
    seed: int = 1,
    num_steps: int = 128,
    num_minibatches: int = 4,
    update_epochs: int = 4,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_coef: float = 0.2,
    ent_coef: float = 0.01,
    vf_coef: float = 0.5,
    max_grad_norm: float = 0.5,
    anneal_lr: bool = True,
    norm_adv: bool = True,
    clip_vloss: bool = True,
    target_kl: float | None = None,
    run_name: str = "tokenboard",
    device: str | torch.device = "cpu",
) -> Agent:

    torch.manual_seed(seed)
    np.random.seed(seed)

    writer = SummaryWriter(f"runs/{run_name}")

    obs_shape = envs.single_observation_space.shape
    act_dim = envs.single_action_space.n
    obs_dim = int(np.prod(obs_shape))

    agent = Agent(obs_dim=obs_dim, act_dim=act_dim).to(device)
    optimizer = optim.Adam(agent.parameters(), lr=learning_rate, eps=1e-5)

    num_envs = envs.num_envs
    batch_size = int(num_envs * num_steps)
    minibatch_size = int(batch_size // num_minibatches)
    num_updates = max(1, total_timesteps // batch_size)

    obs = torch.zeros((num_steps, num_envs) + obs_shape, device=device)
    actions = torch.zeros((num_steps, num_envs), device=device)
    logprobs = torch.zeros((num_steps, num_envs), device=device)
    rewards = torch.zeros((num_steps, num_envs), device=device)
    dones = torch.zeros((num_steps, num_envs), device=device)
    values = torch.zeros((num_steps, num_envs), device=device)

    global_step = 0
    start_time = time.time()

    reset_out = envs.reset()
    next_obs = reset_out[0] if isinstance(reset_out, tuple) else reset_out
    next_obs = torch.as_tensor(next_obs, device=device, dtype=torch.float32)
    next_done = torch.zeros(num_envs, device=device)

    for update in range(1, num_updates + 1):
        if anneal_lr:
            frac = 1.0 - (update - 1.0) / num_updates
            optimizer.param_groups[0]["lr"] = frac * learning_rate

        episodic_returns = []

        for step in range(num_steps):
            global_step += num_envs
            obs[step] = next_obs
            dones[step] = next_done

            with torch.no_grad():
                action, logprob, _, value = agent.get_action_and_value(next_obs.view(num_envs, -1))
                values[step] = value.view(-1)
            actions[step] = action
            logprobs[step] = logprob

            step_out = envs.step(action.cpu().numpy())
            if len(step_out) == 5:
                next_obs_np, reward, terminated, truncated, infos = step_out
                done = np.logical_or(terminated, truncated)
            else:
                next_obs_np, reward, done, infos = step_out

            rewards[step] = torch.as_tensor(reward, device=device, dtype=torch.float32).view(-1)
            next_obs = torch.as_tensor(next_obs_np, device=device, dtype=torch.float32)
            next_done = torch.as_tensor(done, device=device, dtype=torch.float32)

            if isinstance(infos, dict) and "episode" in infos and "r" in infos["episode"]:
                r = infos["episode"]["r"]
                if np.isscalar(r):
                    episodic_returns.append(float(r))
                else:
                    for val in np.array(r).flatten().tolist():
                        if val is not None:
                            episodic_returns.append(float(val))

        with torch.no_grad():
            next_value = agent.get_value(next_obs.view(num_envs, -1)).view(1, -1)

            advantages = torch.zeros_like(rewards, device=device)
            lastgaelam = torch.zeros(num_envs, device=device)
            for t in reversed(range(num_steps)):
                if t == num_steps - 1:
                    nextnonterminal = 1.0 - next_done
                    nextvalues = next_value.view(-1)
                else:
                    nextnonterminal = 1.0 - dones[t + 1]
                    nextvalues = values[t + 1]
                delta = rewards[t] + gamma * nextvalues * nextnonterminal - values[t]
                lastgaelam = delta + gamma * gae_lambda * nextnonterminal * lastgaelam
                advantages[t] = lastgaelam
            returns = advantages + values

        b_obs = obs.reshape((batch_size,) + obs_shape)
        b_actions = actions.reshape((batch_size,))
        b_logprobs = logprobs.reshape((batch_size,))
        b_advantages = advantages.reshape((batch_size,))
        b_returns = returns.reshape((batch_size,))
        b_values = values.reshape((batch_size,))

        b_inds = np.arange(batch_size)
        clipfracs = []
        for epoch in range(update_epochs):
            np.random.shuffle(b_inds)
            for start in range(0, batch_size, minibatch_size):
                end = start + minibatch_size
                mb_inds = b_inds[start:end]

                _, newlogprob, entropy, newvalue = agent.get_action_and_value(
                    b_obs[mb_inds].view(len(mb_inds), -1),
                    b_actions[mb_inds].long(),
                )
                logratio = newlogprob - b_logprobs[mb_inds]
                ratio = logratio.exp()

                with torch.no_grad():
                    approx_kl = ((ratio - 1) - logratio).mean()
                    clipfracs.append(((ratio - 1.0).abs() > clip_coef).float().mean().item())

                mb_adv = b_advantages[mb_inds]
                if norm_adv:
                    mb_adv = (mb_adv - mb_adv.mean()) / (mb_adv.std() + 1e-8)

                pg_loss1 = -mb_adv * ratio
                pg_loss2 = -mb_adv * torch.clamp(ratio, 1 - clip_coef, 1 + clip_coef)
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()

                newvalue = newvalue.view(-1)
                if clip_vloss:
                    v_loss_unclipped = (newvalue - b_returns[mb_inds]) ** 2
                    v_clipped = b_values[mb_inds] + torch.clamp(newvalue - b_values[mb_inds], -clip_coef, clip_coef)
                    v_loss_clipped = (v_clipped - b_returns[mb_inds]) ** 2
                    v_loss = 0.5 * torch.max(v_loss_unclipped, v_loss_clipped).mean()
                else:
                    v_loss = 0.5 * ((newvalue - b_returns[mb_inds]) ** 2).mean()

                entropy_loss = entropy.mean()
                loss = pg_loss - ent_coef * entropy_loss + vf_coef * v_loss

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(agent.parameters(), max_grad_norm)
                optimizer.step()

            if target_kl is not None and approx_kl.item() > target_kl:
                break

        sps = int(global_step / max(1e-6, (time.time() - start_time)))
        writer.add_scalar("charts/SPS", sps, global_step)
        writer.add_scalar("charts/learning_rate", optimizer.param_groups[0]["lr"], global_step)
        writer.add_scalar("losses/policy_loss", pg_loss.item(), global_step)
        writer.add_scalar("losses/value_loss", v_loss.item(), global_step)
        writer.add_scalar("losses/entropy", entropy_loss.item(), global_step)
        writer.add_scalar("losses/approx_kl", approx_kl.item(), global_step)
        writer.add_scalar("losses/clipfrac", float(np.mean(clipfracs)), global_step)

        if episodic_returns:
            writer.add_scalar("charts/episodic_return_mean", float(np.mean(episodic_returns)), global_step)

        if update % 10 == 0:
            print(f"[update {update}/{num_updates}] SPS={sps} return_mean={np.mean(episodic_returns) if episodic_returns else 'n/a'}")

    writer.close()
    return agent
